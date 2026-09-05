from __future__ import annotations

import json
import re
import uuid

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.repositories.documents import DocumentRepository
from app.repositories.study import StudyRepository
from app.schemas.study import StudyContent, StudyGenerate

TYPE_INSTRUCTIONS = {
    "summary": "Write a faithful summary in summary.", "key_points": "Put the essential facts in key_points.",
    "short_notes": "Put concise revision notes in notes.", "explanation": "Explain the topic clearly in explanation.",
    "quiz": "Create the requested number of quiz questions with answer, explanation, options, and source_ids.",
    "flashcards": "Create the requested number of flashcards with front, back, and source_ids.",
    "vocabulary": "Extract important terms with definitions, synonyms, translation when useful, and source_ids.",
    "synonyms": "Put useful synonyms for the supplied term or phrase in synonyms.",
    "translation": "Put the translated result in translated_text.",
}

TYPE_FIELDS = {
    "summary": "summary", "key_points": "key_points", "short_notes": "notes",
    "explanation": "explanation", "quiz": "quiz", "flashcards": "flashcards",
    "vocabulary": "vocabulary", "synonyms": "synonyms", "translation": "translated_text",
}

TYPE_SCHEMAS = {
    "summary": '{"summary":"faithful summary"}',
    "key_points": '{"key_points":["essential fact"]}',
    "short_notes": '{"notes":["concise revision note"]}',
    "explanation": '{"explanation":"clear explanation"}',
    "quiz": '{"quiz":[{"question":"...","options":["..."],"answer":"...","explanation":"...","source_ids":["S1"]}]}',
    "flashcards": '{"flashcards":[{"front":"...","back":"...","source_ids":["S1"]}]}',
    "vocabulary": '{"vocabulary":[{"term":"...","definition":"...","synonyms":["..."],"translation":null,"source_ids":["S1"]}]}',
    "synonyms": '{"synonyms":["useful synonym"]}',
    "translation": '{"translated_text":"complete translation"}',
}


class StudyService:
    def __init__(self, session: AsyncSession, llm, embeddings):
        self.session, self.llm, self.embeddings = session, llm, embeddings
        self.repository, self.documents = StudyRepository(session), DocumentRepository(session)

    @staticmethod
    def _json(text: str) -> dict:
        decoder = json.JSONDecoder()
        for match in re.finditer(r"\{", text):
            try:
                value, _ = decoder.raw_decode(text[match.start():])
                if isinstance(value, dict):
                    return value
            except json.JSONDecodeError:
                continue
        raise ValueError("No valid JSON object returned")

    @staticmethod
    def _has_requested_content(kind: str, content: StudyContent) -> bool:
        values = {
            "summary": content.summary, "key_points": content.key_points, "short_notes": content.notes,
            "explanation": content.explanation, "quiz": content.quiz, "flashcards": content.flashcards,
            "vocabulary": content.vocabulary, "synonyms": content.synonyms, "translation": content.translated_text,
        }
        return bool(values[kind])

    async def _context(self, user_id, payload: StudyGenerate):
        refs, sections = [], []
        if payload.text and payload.text.strip(): sections.append(payload.text.strip())
        if payload.document_id:
            document = await self.documents.get_owned(payload.document_id, user_id)
            if document is None: raise AppError("document_not_found", "Document not found", status_code=404)
            if document.status != "ready": raise AppError("document_not_ready", "Document processing is not complete", status_code=409)
            query = f"{payload.artifact_type} {payload.text or document.title}"
            vector = (await self.embeddings.embed([query], "query"))[0]
            rows = await self.documents.search(user_id, vector, min(12, max(payload.count, 6)), payload.document_id)
            for index, (chunk, _) in enumerate(rows, 1):
                ref_id = f"S{index}"
                refs.append({"id": ref_id, "chunk_id": str(chunk.id), "document_id": str(chunk.document_id),
                             "page_number": chunk.page_number, "excerpt": chunk.content[:280]})
                sections.append(f"[{ref_id}] {chunk.content}")
        return "\n\n".join(sections), refs

    async def generate(self, user_id: uuid.UUID, payload: StudyGenerate):
        if payload.conversation_id and not await self.repository.conversation_owned(payload.conversation_id, user_id):
            raise AppError("conversation_not_found", "Conversation not found", status_code=404)
        context, refs = await self._context(user_id, payload)
        allowed_ids = {item["id"] for item in refs}
        language = "Kinyarwanda" if payload.language == "rw" else "English"
        prompt = (f"Create only a {payload.artifact_type.replace('_', ' ')} for {payload.audience} at "
                  f"{payload.difficulty} difficulty and {payload.length} length, written in {language}. "
                  f"{TYPE_INSTRUCTIONS[payload.artifact_type]} Create exactly {payload.count} items when a list is requested. "
                  f"Return one JSON object with exactly this shape and no other study sections: {TYPE_SCHEMAS[payload.artifact_type]}. "
                  "Do not include Markdown fences or commentary. Use only supplied source IDs and never invent facts.\n\nSOURCE MATERIAL:\n" + context)
        errors = ""
        for attempt in range(2):
            response = await self.llm.complete([
                {"role": "system", "content": "You are EVA Study. Produce valid structured learning material grounded in the supplied content."},
                {"role": "user", "content": prompt + errors},
            ])
            try:
                content = StudyContent.model_validate(self._json(response))
                if not self._has_requested_content(payload.artifact_type, content):
                    raise ValueError(f"Missing {payload.artifact_type} content")
                requested_field = TYPE_FIELDS[payload.artifact_type]
                content = StudyContent.model_validate({requested_field: getattr(content, requested_field)})
                break
            except (ValueError, json.JSONDecodeError, ValidationError) as exc:
                if attempt: raise AppError("invalid_study_output", "The AI provider returned invalid study material", status_code=502) from exc
                errors = (f"\nYour previous response was invalid. Return only a valid JSON object with exactly "
                          f"this shape: {TYPE_SCHEMAS[payload.artifact_type]}")
        data = content.model_dump()
        for collection in (data["quiz"], data["flashcards"], data["vocabulary"]):
            for item in collection:
                item["source_ids"] = [source for source in item["source_ids"] if source in allowed_ids]
                if refs and not item["source_ids"]: item["source_ids"] = [refs[0]["id"]]
        artifact = await self.repository.create(
            user_id=user_id, conversation_id=payload.conversation_id, document_id=payload.document_id,
            artifact_type=payload.artifact_type, title=f"{payload.artifact_type.replace('_', ' ').title()} study set",
            input_text=payload.text.strip() if payload.text else None, language=payload.language, difficulty=payload.difficulty,
            audience=payload.audience, length=payload.length, content=data, source_refs=refs,
            provider=self.llm.__class__.__name__, model=getattr(self.llm, "model", None),
        )
        await self.session.commit(); await self.session.refresh(artifact); return artifact
