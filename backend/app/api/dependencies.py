from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import Depends, Request
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError
from app.db.session import get_session
from app.models import User
from app.services.chat_service import ChatService
from app.services.llm_service import build_llm_service


@dataclass(frozen=True)
class CurrentUser:
    id: uuid.UUID
    role: str


async def get_current_user(request: Request, session: AsyncSession = Depends(get_session)) -> CurrentUser:
    authorization = request.headers.get("Authorization", "")
    if not authorization.lower().startswith("bearer "):
        raise AppError("authentication_required", "Authentication is required", status_code=401)
    token = authorization.split(" ", 1)[1].strip()
    settings: Settings = request.app.state.settings
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        user_id = uuid.UUID(payload["sub"])
    except (JWTError, KeyError, ValueError, TypeError):
        raise AppError("invalid_token", "The access token is invalid or expired", status_code=401)
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise AppError("invalid_token", "The access token is invalid or expired", status_code=401)
    return CurrentUser(id=user.id, role=user.role)


async def get_chat_service(request: Request, session: AsyncSession = Depends(get_session)) -> ChatService:
    return ChatService(session, build_llm_service(request.app.state.settings))
