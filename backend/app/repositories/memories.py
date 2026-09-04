from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Memory


class MemoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_owned(self, memory_id: uuid.UUID, user_id: uuid.UUID) -> Memory | None:
        return await self.session.scalar(select(Memory).where(Memory.id == memory_id, Memory.user_id == user_id))

    async def list_owned(self, user_id: uuid.UUID, status: str | None, offset: int, limit: int):
        filters = [Memory.user_id == user_id]
        if status:
            filters.append(Memory.status == status)
        total = await self.session.scalar(select(func.count()).select_from(Memory).where(*filters)) or 0
        rows = await self.session.scalars(select(Memory).where(*filters).order_by(Memory.updated_at.desc()).offset(offset).limit(limit))
        return list(rows), total

    async def active_count(self, user_id: uuid.UUID) -> int:
        now = datetime.now(UTC)
        return await self.session.scalar(select(func.count()).select_from(Memory).where(
            Memory.user_id == user_id, Memory.status.in_(("proposed", "approved")),
            or_(Memory.expires_at.is_(None), Memory.expires_at > now),
        )) or 0

    async def duplicate(self, user_id: uuid.UUID, category: str, content_hash: str, exclude_id: uuid.UUID | None = None):
        filters = [Memory.user_id == user_id, Memory.category == category, Memory.content_hash == content_hash,
                   Memory.status.in_(("proposed", "approved"))]
        if exclude_id:
            filters.append(Memory.id != exclude_id)
        return await self.session.scalar(select(Memory).where(*filters))

    async def has_approved(self, user_id: uuid.UUID) -> bool:
        now = datetime.now(UTC)
        value = await self.session.scalar(select(Memory.id).where(
            Memory.user_id == user_id, Memory.status == "approved", Memory.deleted_at.is_(None),
            or_(Memory.expires_at.is_(None), Memory.expires_at > now), Memory.embedding.is_not(None),
        ).limit(1))
        return value is not None

    async def retrieve_approved(self, user_id: uuid.UUID, query_embedding: list[float], limit: int) -> list[Memory]:
        now = datetime.now(UTC)
        rows = await self.session.scalars(select(Memory).where(
            Memory.user_id == user_id, Memory.status == "approved", Memory.deleted_at.is_(None),
            or_(Memory.expires_at.is_(None), Memory.expires_at > now), Memory.embedding.is_not(None),
        ).order_by(Memory.embedding.cosine_distance(query_embedding)).limit(limit))
        return list(rows)

    async def delete(self, memory: Memory) -> None:
        await self.session.delete(memory)
