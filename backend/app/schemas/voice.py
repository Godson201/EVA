from __future__ import annotations

import uuid
from datetime import datetime
from pydantic import BaseModel


class VoiceConsentDisclosure(BaseModel):
    version: str
    title: str
    risks: list[str]
    required_assertions: list[str]


class VoiceProfileRead(BaseModel):
    id: uuid.UUID
    name: str
    language: str | None
    status: str
    consent_version: str | None
    purpose: str | None
    consented_at: datetime | None
    revoked_at: datetime | None
    quality_metadata: dict
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class VoiceProfileList(BaseModel):
    items: list[VoiceProfileRead]
    total: int
