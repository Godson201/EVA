from __future__ import annotations

import uuid
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Conversation, StudyArtifact


class StudyRepository:
    def __init__(self, session: AsyncSession): self.session = session

    async def conversation_owned(self, conversation_id, user_id):
        return await self.session.scalar(select(Conversation.id).where(Conversation.id == conversation_id, Conversation.user_id == user_id))

    async def create(self, **values):
        artifact = StudyArtifact(**values); self.session.add(artifact); await self.session.flush(); return artifact

    async def get_owned(self, artifact_id: uuid.UUID, user_id: uuid.UUID):
        return await self.session.scalar(select(StudyArtifact).where(StudyArtifact.id == artifact_id, StudyArtifact.user_id == user_id))

    async def list_owned(self, user_id, artifact_type, offset, limit):
        filters = [StudyArtifact.user_id == user_id]
        if artifact_type: filters.append(StudyArtifact.artifact_type == artifact_type)
        total = await self.session.scalar(select(func.count()).select_from(StudyArtifact).where(*filters)) or 0
        rows = await self.session.scalars(select(StudyArtifact).where(*filters).order_by(StudyArtifact.created_at.desc()).offset(offset).limit(limit))
        return list(rows), total

    async def delete(self, artifact): await self.session.delete(artifact)
