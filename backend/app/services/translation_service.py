from __future__ import annotations

import asyncio
import re
import threading
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError
from app.repositories.translations import TranslationRepository
from app.schemas.translation import TranslationMode
from app.services.language_detection_service import LanguageDetectionService

LANGUAGE_CODES = {"en": "eng_Latn", "rw": "kin_Latn"}
MODE_GUIDANCE = {
    TranslationMode.NATURAL: "Use natural, idiomatic language while preserving meaning.",
    TranslationMode.SIMPLE: "Use simple vocabulary and short, clear sentences.",
    TranslationMode.PROFESSIONAL: "Use polished professional language.",
    TranslationMode.ACADEMIC: "Use precise academic language and preserve technical terms.",
    TranslationMode.CALL_CENTER: "Use courteous, concise call-center language suitable for speaking to a customer.",
}


def split_translation_text(text: str, max_chars: int = 1200) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    chunks: list[str] = []
    for paragraph in paragraphs:
        while len(paragraph) > max_chars:
            cut = paragraph.rfind(" ", 0, max_chars)
            cut = cut if cut > max_chars // 2 else max_chars
            chunks.append(paragraph[:cut].strip())
            paragraph = paragraph[cut:].strip()
        if paragraph:
            chunks.append(paragraph)
    return chunks or [text.strip()]


class NLLBTranslationService:
    _model = None
    _tokenizer = None
    _lock = threading.Lock()

    def __init__(self, settings: Settings):
        self.model_name = settings.translation_model
        self.max_input_chars = settings.translation_max_input_chars

    @classmethod
    def _load(cls, model_name: str):
        if cls._model is None or cls._tokenizer is None:
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
            cls._tokenizer = AutoTokenizer.from_pretrained(model_name)
            cls._model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
            cls._model.eval()
        return cls._tokenizer, cls._model

    def _translate_sync(self, text: str, source: str, target: str) -> str:
        with self._lock:
            tokenizer, model = self._load(self.model_name)
            tokenizer.src_lang = LANGUAGE_CODES[source]
            outputs = []
            for chunk in split_translation_text(text):
                inputs = tokenizer(chunk, return_tensors="pt", truncation=True, max_length=512)
                tokens = model.generate(
                    **inputs,
                    forced_bos_token_id=tokenizer.convert_tokens_to_ids(LANGUAGE_CODES[target]),
                    max_new_tokens=512,
                )
                outputs.append(tokenizer.batch_decode(tokens, skip_special_tokens=True)[0].strip())
            return "\n\n".join(outputs)

    async def translate(self, text: str, source: str, target: str) -> str:
        if len(text) > self.max_input_chars:
            raise AppError("translation_too_large", f"Translation input exceeds {self.max_input_chars} characters", status_code=413)
        if source not in LANGUAGE_CODES or target not in LANGUAGE_CODES or source == target:
            raise AppError("invalid_language_pair", "Translation requires different English and Kinyarwanda languages", status_code=422)
        try:
            return await asyncio.to_thread(self._translate_sync, text, source, target)
        except AppError:
            raise
        except Exception as exc:
            raise AppError("translation_provider_error", "The translation model is unavailable", status_code=503) from exc


class TranslationService:
    def __init__(self, session: AsyncSession, base_translator, llm=None, detector=None):
        self.session = session
        self.repository = TranslationRepository(session)
        self.base_translator = base_translator
        self.llm = llm
        self.detector = detector or LanguageDetectionService()

    async def translate(self, user_id: uuid.UUID, text: str, target: str, mode: TranslationMode, source: str | None = None, conversation_id=None):
        detected_automatically = source is None
        source = source or self.detector.detect(text)[0]
        if source == target:
            raise AppError("invalid_language_pair", "Detected source language matches the target language", status_code=422)

        fallback_used = False
        provider = "nllb"
        translated = None
        if mode != TranslationMode.DIRECT and self.llm is not None:
            language_name = "English" if target == "en" else "Kinyarwanda"
            messages = [
                {"role": "system", "content": f"Translate into {language_name}. {MODE_GUIDANCE[mode]} Return only the translation."},
                {"role": "user", "content": text},
            ]
            try:
                translated = await self.llm.complete(messages)
                provider = self.llm.__class__.__name__
            except AppError:
                fallback_used = True
        if translated is None:
            translated = await self.base_translator.translate(text, source, target)

        item = await self.repository.create(
            user_id=user_id, conversation_id=conversation_id, source_text=text,
            translated_text=translated, source_language=source, target_language=target,
            mode=mode.value, provider=provider,
        )
        await self.session.commit()
        await self.session.refresh(item)
        return item, detected_automatically, fallback_used
