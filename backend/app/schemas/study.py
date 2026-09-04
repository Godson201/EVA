from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

StudyType = Literal["summary", "key_points", "short_notes", "explanation", "quiz", "flashcards", "vocabulary", "synonyms", "translation"]


class QuizItem(BaseModel):
    question: str
    options: list[str] = Field(default_factory=list)
    answer: str
    explanation: str = ""
    source_ids: list[str] = Field(default_factory=list)


class FlashcardItem(BaseModel):
    front: str
    back: str
    source_ids: list[str] = Field(default_factory=list)


class VocabularyEntry(BaseModel):
    term: str
    definition: str
    synonyms: list[str] = Field(default_factory=list)
    translation: str | None = None
    source_ids: list[str] = Field(default_factory=list)


class StudyContent(BaseModel):
    summary: str | None = None
    key_points: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    explanation: str | None = None
    quiz: list[QuizItem] = Field(default_factory=list)
    flashcards: list[FlashcardItem] = Field(default_factory=list)
    vocabulary: list[VocabularyEntry] = Field(default_factory=list)
    synonyms: list[str] = Field(default_factory=list)
    translated_text: str | None = None


class StudyGenerate(BaseModel):
    artifact_type: StudyType
    text: str | None = Field(default=None, max_length=50_000)
    document_id: uuid.UUID | None = None
    conversation_id: uuid.UUID | None = None
    language: Literal["en", "rw"] = "en"
    difficulty: Literal["beginner", "intermediate", "advanced"] = "intermediate"
    audience: str = Field(default="general", min_length=1, max_length=100)
    length: Literal["short", "medium", "long"] = "medium"
    count: int = Field(default=5, ge=1, le=20)

    @model_validator(mode="after")
    def source_required(self):
        if not (self.text and self.text.strip()) and self.document_id is None:
            raise ValueError("text or document_id is required")
        return self


class SourceReference(BaseModel):
    id: str
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    page_number: int | None
    excerpt: str


class StudyArtifactRead(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID | None
    document_id: uuid.UUID | None
    artifact_type: str
    title: str
    language: str
    difficulty: str
    audience: str
    length: str
    content: StudyContent
    source_refs: list[SourceReference]
    provider: str | None
    model: str | None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class StudyArtifactList(BaseModel):
    items: list[StudyArtifactRead]
    total: int
