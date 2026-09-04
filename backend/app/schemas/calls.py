from __future__ import annotations

import uuid
from typing import Literal
from pydantic import BaseModel, Field


class CallTicket(BaseModel):
    ticket: str
    expires_in: int
    websocket_path: str = "/api/v1/calls/ws"


class CallConfig(BaseModel):
    source_language: Literal["auto", "en", "rw"] = "auto"
    target_language: Literal["en", "rw"] = "en"


class TextTurn(BaseModel):
    type: Literal["text_turn"]
    text: str = Field(min_length=1, max_length=5000)
    speaker: Literal["customer", "agent"] = "customer"


class AudioChunk(BaseModel):
    type: Literal["audio_chunk"]
    sequence: int = Field(ge=0)
    audio: str = Field(min_length=1, max_length=100_000)


class CallWrapUp(BaseModel):
    summary: str
    action_items: list[str] = Field(default_factory=list)


class CallSessionRead(BaseModel):
    id: uuid.UUID
    status: str
    source_language: str | None
    target_language: str | None
    transcript: list
    summary: str | None
    action_items: list
    sentiment_cues: list
    model_config = {"from_attributes": True}
