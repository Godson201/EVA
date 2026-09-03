from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class TranslationMode(StrEnum):
    DIRECT = "direct"
    NATURAL = "natural"
    SIMPLE = "simple"
    PROFESSIONAL = "professional"
    ACADEMIC = "academic"
    CALL_CENTER = "call-center"


class TranslationCreate(BaseModel):
    text: str = Field(min_length=1, max_length=100_000)
    source_language: str | None = Field(default=None, pattern="^(en|rw)$")
    target_language: str = Field(pattern="^(en|rw)$")
    mode: TranslationMode = TranslationMode.NATURAL
    conversation_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def languages_must_differ(self):
        if self.source_language and self.source_language == self.target_language:
            raise ValueError("source_language and target_language must differ")
        return self


class TranslationRead(BaseModel):
    id: uuid.UUID
    source_text: str
    translated_text: str
    source_language: str
    target_language: str
    mode: str
    provider: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TranslationResult(BaseModel):
    translation: TranslationRead
    detected_automatically: bool
    fallback_used: bool = False


class TranslationList(BaseModel):
    items: list[TranslationRead]
    total: int


class LegacyTranslationRequest(BaseModel):
    text: str = Field(min_length=1, max_length=100_000)
    source_lang: str | None = Field(default=None, pattern="^(en|rw)$")
    target_lang: str = Field(pattern="^(en|rw)$")
    mode: TranslationMode = TranslationMode.NATURAL
