from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Conversation, Message


class ConversationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, user_id: uuid.UUID, title: str | None, language: str | None) -> Conversation:
        conversation = Conversation(user_id=user_id, title=title, language=language)
        self.session.add(conversation)
        await self.session.flush()
        return conversation

    async def get_owned(self, conversation_id: uuid.UUID, user_id: uuid.UUID) -> Conversation | None:
        return await self.session.scalar(select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
            Conversation.archived_at.is_(None),
        ))

    async def list_owned(self, user_id: uuid.UUID, offset: int, limit: int) -> tuple[list[Conversation], int]:
        where = (Conversation.user_id == user_id, Conversation.archived_at.is_(None))
        total = await self.session.scalar(select(func.count()).select_from(Conversation).where(*where)) or 0
        result = await self.session.scalars(
            select(Conversation).where(*where).order_by(Conversation.updated_at.desc()).offset(offset).limit(limit)
        )
        return list(result), total

    async def messages(self, conversation_id: uuid.UUID) -> list[Message]:
        result = await self.session.scalars(
            select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at, Message.id)
        )
        return list(result)

    async def recent_messages(self, conversation_id: uuid.UUID, limit: int = 40) -> list[Message]:
        result = await self.session.scalars(
            select(Message).where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc(), Message.id.desc()).limit(limit)
        )
        return list(reversed(list(result)))

    async def add_message(self, conversation_id: uuid.UUID, role: str, content: str, **values) -> Message:
        message = Message(conversation_id=conversation_id, role=role, content=content, **values)
        self.session.add(message)
        await self.session.flush()
        return message

    async def archive(self, conversation: Conversation) -> None:
        conversation.archived_at = func.now()
        await self.session.flush()

    async def touch(self, conversation: Conversation) -> None:
        conversation.updated_at = func.now()
        await self.session.flush()
