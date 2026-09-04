from __future__ import annotations

import uuid
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=100, pattern=r"^[A-Za-z0-9_.-]+$")
    email: str = Field(min_length=5, max_length=320, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    password: str = Field(min_length=8, max_length=1024)
    full_name: str | None = Field(default=None, max_length=255)


class ForgotPasswordRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=320)


class ForgotPasswordResponse(BaseModel):
    message: str
    reset_token: str | None = None


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=20, max_length=512)
    new_password: str = Field(min_length=8, max_length=1024)


class MessageResponse(BaseModel):
    message: str


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
