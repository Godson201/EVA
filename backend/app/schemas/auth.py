from __future__ import annotations

import uuid
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


class UserSession(BaseModel):
    id: uuid.UUID
    username: str
    email: str
    full_name: str | None
    role: str
    profile_type: str
    model_config = {"from_attributes": True}


class SessionResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserSession
