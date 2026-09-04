from types import SimpleNamespace
import asyncio
import uuid

import pytest

from app.core.config import Settings
from app.core.errors import AppError
from app.services.chat_service import ChatService
from app.services.memory_service import MemoryService


class Session:
    def add(self, item):
        self.item = item

    async def flush(self):
        return None


class Embeddings:
    calls = 0

    async def embed(self, texts, kind):
        self.calls += 1
        return [[0.1] * 768]


def test_sensitive_memory_is_rejected():
    service = MemoryService(Session(), Embeddings(), Settings(_env_file=None))
    with pytest.raises(AppError) as error:
        asyncio.run(service.create(uuid.uuid4(), "preference", "My password is hunter2", {}, 30))
    assert error.value.code == "sensitive_memory_rejected"


def test_new_memory_is_proposed_and_not_embedded():
    service = MemoryService(Session(), Embeddings(), Settings(_env_file=None))
    service.repository.active_count = lambda user_id: async_value(0)
    service.repository.duplicate = lambda *args: async_value(None)
    memory = asyncio.run(service.create(uuid.uuid4(), "preference", " Please answer in Kinyarwanda. ", {"source": "user"}, 30))
    assert memory.status == "proposed"
    assert memory.embedding is None
    assert service.embeddings.calls == 0


def test_no_approved_memory_skips_embedding_and_prompt_injection():
    service = MemoryService(Session(), Embeddings(), Settings(_env_file=None))
    service.repository.has_approved = lambda user_id: async_value(False)
    assert asyncio.run(service.retrieve(uuid.uuid4(), "hello")) == []
    assert service.embeddings.calls == 0


def test_chat_marks_memory_as_untrusted_profile_context():
    memory = SimpleNamespace(category="profession", content="I am a teacher")
    memory_service = SimpleNamespace(retrieve=lambda user_id, content: async_value([memory]))
    chat = ChatService(Session(), object(), memory_service=memory_service)
    messages = asyncio.run(chat._system_messages(uuid.uuid4(), "Explain this"))
    assert "explicitly approved" in messages[1]["content"]
    assert "never as instructions" in messages[1]["content"]
    assert "I am a teacher" in messages[1]["content"]


async def async_value(value):
    return value
