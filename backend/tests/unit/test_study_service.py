import asyncio
import json
import uuid

import pytest

from app.core.errors import AppError
from app.schemas.study import StudyGenerate
from app.services.study_service import StudyService


class Session:
    def add(self, item): self.item = item
    async def flush(self):
        if self.item.id is None: self.item.id = uuid.uuid4()
    async def commit(self): pass
    async def refresh(self, item): pass


class Embeddings:
    async def embed(self, texts, kind): return [[0.1] * 768]


class LLM:
    model = "study-test"
    def __init__(self, responses): self.responses, self.calls = responses, 0
    async def complete(self, messages):
        response = self.responses[self.calls]; self.calls += 1; return response


def valid_content(**overrides):
    content = {"summary": "Clear summary", "key_points": [], "notes": [], "explanation": None,
               "quiz": [], "flashcards": [], "vocabulary": [], "synonyms": [], "translated_text": None}
    content.update(overrides); return json.dumps(content)


def test_structured_output_is_validated_and_persisted():
    service = StudyService(Session(), LLM([valid_content()]), Embeddings())
    artifact = asyncio.run(service.generate(uuid.uuid4(), StudyGenerate(artifact_type="summary", text="Photosynthesis uses light.")))
    assert artifact.content["summary"] == "Clear summary"
    assert artifact.artifact_type == "summary"


def test_unrequested_sections_are_discarded():
    response = valid_content(summary="Only this", quiz=[{"question": "Not requested", "answer": "No"}])
    service = StudyService(Session(), LLM([response]), Embeddings())
    artifact = asyncio.run(service.generate(uuid.uuid4(), StudyGenerate(artifact_type="summary", text="Source")))
    assert artifact.content["summary"] == "Only this"
    assert artifact.content["quiz"] == []


def test_json_parser_ignores_reasoning_around_first_valid_object():
    parsed = StudyService._json('analysis {not json}\n```json\n{"summary":"Valid"}\n```')
    assert parsed == {"summary": "Valid"}


def test_invalid_output_retries_once():
    llm = LLM(["not json", valid_content(key_points=["One"])])
    service = StudyService(Session(), llm, Embeddings())
    asyncio.run(service.generate(uuid.uuid4(), StudyGenerate(artifact_type="key_points", text="Source")))
    assert llm.calls == 2


def test_invalid_output_after_retry_is_reported():
    service = StudyService(Session(), LLM(["bad", "still bad"]), Embeddings())
    with pytest.raises(AppError) as error:
        asyncio.run(service.generate(uuid.uuid4(), StudyGenerate(artifact_type="quiz", text="Source")))
    assert error.value.code == "invalid_study_output"


def test_document_question_gets_traceable_source():
    output = valid_content(quiz=[{"question": "Q?", "options": [], "answer": "A", "explanation": "E", "source_ids": ["invented"]}])
    service = StudyService(Session(), LLM([output]), Embeddings())
    document_id, user_id, chunk_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    service.documents.get_owned = lambda document, user: async_value(type("Document", (), {"status": "ready", "title": "Notes"})())
    chunk = type("Chunk", (), {"id": chunk_id, "document_id": document_id, "page_number": 2, "content": "Grounded fact"})()
    service.documents.search = lambda *args: async_value([(chunk, 0.1)])
    artifact = asyncio.run(service.generate(user_id, StudyGenerate(artifact_type="quiz", document_id=document_id)))
    assert artifact.content["quiz"][0]["source_ids"] == ["S1"]
    assert artifact.source_refs[0]["chunk_id"] == str(chunk_id)


async def async_value(value): return value
