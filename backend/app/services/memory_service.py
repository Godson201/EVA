from __future__ import annotations

import hashlib
import re
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError
from app.models import Memory
from app.repositories.memories import MemoryRepository

ALLOWED_CATEGORIES = {"preference", "terminology", "vocabulary", "correction", "profession", "explanation_style", "approved_phrase"}
SENSITIVE_PATTERNS = (
    re.compile(r"\b(?:password|passcode|pin|secret|api[-_ ]?key|access[-_ ]?token|private[-_ ]?key)\b", re.I),
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
)


class MemoryService:
    def __init__(self, session: AsyncSession, embeddings, settings: Settings):
        self.session = session
        self.repository = MemoryRepository(session)
        self.embeddings = embeddings
        self.settings = settings

    def _normalize(self, content: str) -> str:
        return re.sub(r"\s+", " ", content).strip()

    def _validate(self, category: str, content: str) -> str:
        normalized = self._normalize(content)
        if category not in ALLOWED_CATEGORIES:
            raise AppError("invalid_memory_category", "This memory category is not supported", status_code=422)
        if not normalized or len(normalized) > self.settings.memory_max_content_chars:
            raise AppError("invalid_memory_content", f"Memory must contain 1 to {self.settings.memory_max_content_chars} characters", status_code=422)
        if any(pattern.search(normalized) for pattern in SENSITIVE_PATTERNS):
            raise AppError("sensitive_memory_rejected", "Passwords, secrets, identity numbers, and payment-card data cannot be stored as memory", status_code=422)
        return normalized

    @staticmethod
    def _hash(content: str) -> str:
        return hashlib.sha256(content.casefold().encode("utf-8")).hexdigest()

    async def create(self, user_id, category, content, provenance, retention_days, source_message_id=None):
        content = self._validate(category, content)
        if await self.repository.active_count(user_id) >= self.settings.memory_max_items_per_user:
            raise AppError("memory_limit_reached", "Memory limit reached; delete an item before adding another", status_code=409)
        digest = self._hash(content)
        if await self.repository.duplicate(user_id, category, digest):
            raise AppError("duplicate_memory", "This memory already exists", status_code=409)
        days = retention_days or self.settings.memory_max_retention_days
        days = min(days, self.settings.memory_max_retention_days)
        memory = Memory(user_id=user_id, category=category, content=content, content_hash=digest, status="proposed",
                        provenance=provenance, source_message_id=source_message_id,
                        expires_at=datetime.now(UTC) + timedelta(days=days))
        self.session.add(memory)
        await self.session.flush()
        return memory

    async def owned(self, memory_id, user_id):
        memory = await self.repository.get_owned(memory_id, user_id)
        if memory is None:
            raise AppError("memory_not_found", "Memory not found", status_code=404)
        return memory

    async def approve(self, memory_id, user_id):
        memory = await self.owned(memory_id, user_id)
        if memory.status not in {"proposed", "rejected"}:
            raise AppError("invalid_memory_state", "Only proposed or rejected memories can be approved", status_code=409)
        memory.embedding = (await self.embeddings.embed([memory.content], "passage"))[0]
        memory.status, memory.approved_at, memory.rejected_at, memory.deleted_at = "approved", datetime.now(UTC), None, None
        await self.session.flush()
        return memory

    async def reject(self, memory_id, user_id):
        memory = await self.owned(memory_id, user_id)
        if memory.status not in {"proposed", "approved"}:
            raise AppError("invalid_memory_state", "Only proposed or approved memories can be rejected", status_code=409)
        memory.status, memory.rejected_at, memory.approved_at, memory.embedding = "rejected", datetime.now(UTC), None, None
        await self.session.flush()
        return memory

    async def edit(self, memory_id, user_id, category, content, provenance, retention_days):
        memory = await self.owned(memory_id, user_id)
        category = category or memory.category
        content = self._validate(category, content)
        digest = self._hash(content)
        if await self.repository.duplicate(user_id, category, digest, memory.id):
            raise AppError("duplicate_memory", "This memory already exists", status_code=409)
        memory.category, memory.content, memory.content_hash = category, content, digest
        memory.provenance = provenance if provenance is not None else memory.provenance
        if retention_days:
            memory.expires_at = datetime.now(UTC) + timedelta(days=min(retention_days, self.settings.memory_max_retention_days))
        memory.status, memory.embedding, memory.approved_at, memory.rejected_at = "proposed", None, None, None
        await self.session.flush()
        return memory

    async def retrieve(self, user_id, query: str):
        if not await self.repository.has_approved(user_id):
            return []
        vector = (await self.embeddings.embed([query], "query"))[0]
        memories = await self.repository.retrieve_approved(user_id, vector, self.settings.memory_retrieval_limit)
        now = datetime.now(UTC)
        for memory in memories:
            memory.last_used_at = now
        await self.session.flush()
        return memories
