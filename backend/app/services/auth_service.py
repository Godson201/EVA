from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from jose import jwt
from passlib.context import CryptContext
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError
from app.models import PasswordResetToken, RefreshToken, User

passwords = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings):
        self.session, self.settings = session, settings

    @staticmethod
    def _hash(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def _access(self, user: User) -> str:
        now = datetime.now(UTC)
        return jwt.encode({"sub": str(user.id), "role": user.role, "iat": now, "exp": now + timedelta(minutes=self.settings.access_token_minutes)},
                          self.settings.secret_key, algorithm="HS256")

    async def _issue(self, user: User, family_id: uuid.UUID | None = None):
        raw = secrets.token_urlsafe(48)
        token = RefreshToken(user_id=user.id, token_hash=self._hash(raw), family_id=family_id or uuid.uuid4(),
                             expires_at=datetime.now(UTC) + timedelta(days=self.settings.refresh_token_days))
        self.session.add(token)
        await self.session.flush()
        return self._access(user), raw, token

    async def login(self, identifier: str, password: str):
        user = await self.session.scalar(select(User).where(or_(User.username == identifier, User.email == identifier)))
        if user is None or not user.is_active or not user.password_hash or not passwords.verify(password, user.password_hash):
            raise AppError("invalid_credentials", "Invalid username, email, or password", status_code=401)
        user.last_login_at = datetime.now(UTC)
        access, refresh, _ = await self._issue(user)
        await self.session.commit()
        return user, access, refresh

    async def register(self, username: str, email: str, password: str, full_name: str | None):
        username, email = username.strip(), email.strip().lower()
        exists = await self.session.scalar(select(User.id).where(or_(
            func.lower(User.username) == username.lower(), func.lower(User.email) == email,
        )))
        if exists:
            raise AppError("account_exists", "That username or email is already registered", status_code=409)
        user = User(username=username, email=email, password_hash=passwords.hash(password),
                    full_name=(full_name or "").strip() or None, role="USER",
                    profile_type="general_user", provider="email", is_active=True)
        self.session.add(user)
        await self.session.flush()
        access, refresh, _ = await self._issue(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user, access, refresh

    async def request_password_reset(self, identifier: str) -> str | None:
        value = identifier.strip().lower()
        user = await self.session.scalar(select(User).where(or_(
            func.lower(User.username) == value, func.lower(User.email) == value,
        )))
        if user is None or not user.is_active:
            return None
        now = datetime.now(UTC)
        await self.session.execute(update(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None)
        ).values(used_at=now))
        raw = secrets.token_urlsafe(48)
        self.session.add(PasswordResetToken(user_id=user.id, token_hash=self._hash(raw),
                                            expires_at=now + timedelta(minutes=30)))
        await self.session.commit()
        return raw

    async def reset_password(self, raw_token: str, new_password: str) -> None:
        now = datetime.now(UTC)
        token = await self.session.scalar(select(PasswordResetToken).where(
            PasswordResetToken.token_hash == self._hash(raw_token)
        ).with_for_update())
        if token is None or token.used_at is not None or token.expires_at <= now:
            raise AppError("invalid_reset_token", "This password reset link is invalid or expired", status_code=400)
        user = await self.session.get(User, token.user_id)
        if user is None or not user.is_active:
            raise AppError("invalid_reset_token", "This password reset link is invalid or expired", status_code=400)
        user.password_hash = passwords.hash(new_password)
        token.used_at = now
        await self.session.execute(update(RefreshToken).where(
            RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None)
        ).values(revoked_at=now))
        await self.session.commit()

    async def rotate(self, raw_token: str):
        now = datetime.now(UTC)
        token = await self.session.scalar(select(RefreshToken).where(RefreshToken.token_hash == self._hash(raw_token)).with_for_update())
        if token is not None and token.revoked_at is not None:
            await self.session.execute(update(RefreshToken).where(
                RefreshToken.family_id == token.family_id, RefreshToken.revoked_at.is_(None)
            ).values(revoked_at=now))
            await self.session.commit()
            raise AppError("refresh_token_reused", "Refresh session was revoked because an old token was reused", status_code=401)
        if token is None or token.expires_at <= now:
            raise AppError("invalid_refresh_token", "Refresh session is invalid or expired", status_code=401)
        user = await self.session.get(User, token.user_id)
        if user is None or not user.is_active:
            raise AppError("invalid_refresh_token", "Refresh session is invalid or expired", status_code=401)
        access, refresh, replacement = await self._issue(user, token.family_id)
        token.revoked_at, token.replaced_by_id = now, replacement.id
        await self.session.commit()
        return user, access, refresh

    async def logout(self, raw_token: str | None):
        if raw_token:
            token = await self.session.scalar(select(RefreshToken).where(RefreshToken.token_hash == self._hash(raw_token)))
            if token:
                await self.session.execute(update(RefreshToken).where(
                    RefreshToken.family_id == token.family_id, RefreshToken.revoked_at.is_(None)
                ).values(revoked_at=datetime.now(UTC)))
                await self.session.commit()
