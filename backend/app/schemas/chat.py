from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    language: str | None = Field(default=None, max_length=20)


class ConversationRead(BaseModel):
    id: uuid.UUID
    title: str | None
    language: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=50_000)
    language: str | None = Field(default=None, max_length=20)


class MessageRead(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: Literal["user", "assistant", "system"]
    content: str
    language: str | None
    intent: str | None
    status: str
    provider: str | None
    model: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationDetail(ConversationRead):
    messages: list[MessageRead]


class ConversationList(BaseModel):
    items: list[ConversationRead]
    total: int


class ChatResponse(BaseModel):
    user_message: MessageRead
    assistant_message: MessageRead
