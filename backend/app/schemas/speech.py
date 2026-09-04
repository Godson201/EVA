from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class TranscriptionRead(BaseModel):
    id: uuid.UUID
    attachment_id: uuid.UUID | None
    language: str | None
    raw_text: str | None
    corrected_text: str | None
    timestamps: list
    duration_seconds: float | None
    status: str
    model: str | None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class TranscriptionUploadResult(BaseModel):
    transcription: TranscriptionRead
    job_id: uuid.UUID


class TranscriptionList(BaseModel):
    items: list[TranscriptionRead]
    total: int


class SpeechJobRead(BaseModel):
    id: uuid.UUID
    attachment_id: uuid.UUID | None
    transcription_id: uuid.UUID | None
    task_name: str
    status: str
    progress: int
    attempts: int
    error_message: str | None
    result: dict
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class SynthesisRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20_000)
    language: str = Field(pattern="^(en|rw)$")
    voice_profile_id: uuid.UUID | None = None


class SynthesisResult(BaseModel):
    job_id: uuid.UUID
    status: str
