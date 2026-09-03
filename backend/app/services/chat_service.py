from __future__ import annotations

import uuid
import asyncio
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.repositories.conversations import ConversationRepository
from app.services.intent_service import IntentRouter

EVA_SYSTEM_PROMPT = """You are EVA, a helpful English–Kinyarwanda assistant. Respond in the user's language unless they ask for another language. Handle mixed-language input naturally. Be accurate, concise, and honest about uncertainty. Never claim to have read an attachment unless retrieved document context is present. Never create personal memory unless the user explicitly approves it."""


class ChatService:
    def __init__(self, session: AsyncSession, llm, intent_router: IntentRouter | None = None):
        self.session = session
        self.repository = ConversationRepository(session)
        self.llm = llm
        self.intent_router = intent_router or IntentRouter()

    async def create_conversation(self, user_id: uuid.UUID, title: str | None, language: str | None):
        conversation = await self.repository.create(user_id, title, language)
        await self.session.commit()
        await self.session.refresh(conversation)
        return conversation

    async def get_conversation(self, conversation_id: uuid.UUID, user_id: uuid.UUID):
        conversation = await self.repository.get_owned(conversation_id, user_id)
        if conversation is None:
            raise AppError("conversation_not_found", "Conversation not found", status_code=404)
        return conversation

    async def prompt(self, conversation_id: uuid.UUID, user_id: uuid.UUID, content: str, language: str | None):
        conversation = await self.get_conversation(conversation_id, user_id)
        history = await self.repository.recent_messages(conversation.id)
        intent = self.intent_router.classify(content)
        user_message = await self.repository.add_message(conversation.id, "user", content, language=language, intent=intent.value)
        provider_messages = [{"role": "system", "content": EVA_SYSTEM_PROMPT}] + [
            {"role": message.role, "content": message.content} for message in history if message.role in {"user", "assistant"}
        ] + [{"role": "user", "content": content}]
        answer = await self.llm.complete(provider_messages)
        assistant = await self.repository.add_message(
            conversation.id, "assistant", answer, language=language, intent=intent.value,
            provider=self.llm.__class__.__name__, model=getattr(self.llm, "model", None),
        )
        await self.repository.touch(conversation)
        await self.session.commit()
        await self.session.refresh(user_message)
        await self.session.refresh(assistant)
        return user_message, assistant

    async def stream_prompt(self, conversation_id: uuid.UUID, user_id: uuid.UUID, content: str, language: str | None) -> AsyncIterator[str]:
        conversation = await self.get_conversation(conversation_id, user_id)
        history = await self.repository.recent_messages(conversation.id)
        intent = self.intent_router.classify(content)
        await self.repository.add_message(conversation.id, "user", content, language=language, intent=intent.value)
        await self.session.commit()
        provider_messages = [{"role": "system", "content": EVA_SYSTEM_PROMPT}] + [
            {"role": message.role, "content": message.content} for message in history if message.role in {"user", "assistant"}
        ] + [{"role": "user", "content": content}]
        chunks: list[str] = []
        status = "completed"
        try:
            async for chunk in self.llm.stream(provider_messages):
                chunks.append(chunk)
                yield chunk
        except asyncio.CancelledError:
            status = "cancelled"
            raise
        except Exception:
            status = "failed"
            raise
        finally:
            await self.repository.add_message(
                conversation.id, "assistant", "".join(chunks).strip(), language=language,
                intent=intent.value, status=status, provider=self.llm.__class__.__name__,
                model=getattr(self.llm, "model", None),
            )
            await self.repository.touch(conversation)
            await self.session.commit()
