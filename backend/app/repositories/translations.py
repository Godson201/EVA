from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Translation


class TranslationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **values) -> Translation:
        item = Translation(**values)
        self.session.add(item)
        await self.session.flush()
        return item

    async def list_owned(self, user_id: uuid.UUID, offset: int, limit: int) -> tuple[list[Translation], int]:
        total = await self.session.scalar(select(func.count()).select_from(Translation).where(Translation.user_id == user_id)) or 0
        rows = await self.session.scalars(
            select(Translation).where(Translation.user_id == user_id)
            .order_by(Translation.created_at.desc()).offset(offset).limit(limit)
        )
        return list(rows), total
