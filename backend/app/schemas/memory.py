from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

MemoryCategory = Literal["preference", "terminology", "vocabulary", "correction", "profession", "explanation_style", "approved_phrase"]
MemoryStatus = Literal["proposed", "approved", "rejected", "deleted"]


class MemoryCreate(BaseModel):
    category: MemoryCategory
    content: str = Field(min_length=1, max_length=10_000)
    provenance: dict = Field(default_factory=lambda: {"source": "user"})
    retention_days: int | None = Field(default=None, ge=1, le=3650)


class MemoryUpdate(BaseModel):
    category: MemoryCategory | None = None
    content: str = Field(min_length=1, max_length=10_000)
    provenance: dict | None = None
    retention_days: int | None = Field(default=None, ge=1, le=3650)


class MemoryRead(BaseModel):
    id: uuid.UUID
    category: str
    content: str
    status: str
    provenance: dict
    source_message_id: uuid.UUID | None
    approved_at: datetime | None
    rejected_at: datetime | None
    expires_at: datetime | None
    last_used_at: datetime | None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class MemoryList(BaseModel):
    items: list[MemoryRead]
    total: int
