from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
import unittest

from fastapi.testclient import TestClient

from app.api.dependencies import CurrentUser, get_chat_service, get_current_user
from app.core.config import Settings
from app.core.errors import AppError
from app.main import create_app

USER_ID = uuid.uuid4()
OTHER_USER_ID = uuid.uuid4()


def record(**values):
    now = datetime.now(UTC)
    defaults = {"id": uuid.uuid4(), "created_at": now, "updated_at": now}
    defaults.update(values)
    return SimpleNamespace(**defaults)


class FakeRepository:
    def __init__(self):
        self.conversations = {}
        self.message_items = {}

    async def list_owned(self, user_id, offset, limit):
        items = [item for item in self.conversations.values() if item.user_id == user_id]
        return items[offset:offset + limit], len(items)

    async def messages(self, conversation_id):
        return self.message_items.get(conversation_id, [])


class FakeChatService:
    def __init__(self):
        self.repository = FakeRepository()
        self.session = SimpleNamespace(commit=self._commit)

    async def _commit(self):
        return None

    async def create_conversation(self, user_id, title, language):
        item = record(user_id=user_id, title=title, language=language)
        self.repository.conversations[item.id] = item
        return item

    async def get_conversation(self, conversation_id, user_id):
        item = self.repository.conversations.get(conversation_id)
        if item is None or item.user_id != user_id:
            raise AppError("conversation_not_found", "Conversation not found", status_code=404)
        return item

    async def prompt(self, conversation_id, user_id, content, language):
        await self.get_conversation(conversation_id, user_id)
        user_message = record(conversation_id=conversation_id, role="user", content=content, language=language, intent="chat", status="completed", provider=None, model=None)
        assistant = record(conversation_id=conversation_id, role="assistant", content=f"EVA test response: {content}", language=language, intent="chat", status="completed", provider="DeterministicLLMService", model="deterministic-test")
        self.repository.message_items.setdefault(conversation_id, []).extend([user_message, assistant])
        return user_message, assistant

    async def stream_prompt(self, conversation_id, user_id, content, language):
        await self.get_conversation(conversation_id, user_id)
        yield "EVA "
        yield "stream"


class ChatApiTests(unittest.TestCase):
    def setUp(self):
        self.service = FakeChatService()
        app = create_app(Settings(environment="test", _env_file=None), include_legacy=False)
        app.dependency_overrides[get_current_user] = lambda: CurrentUser(USER_ID, "USER")
        app.dependency_overrides[get_chat_service] = lambda: self.service
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()

    def test_conversation_and_message_flow(self):
        created = self.client.post("/api/v1/conversations", json={"title": "Test chat", "language": "rw"})
        self.assertEqual(created.status_code, 201)
        conversation_id = created.json()["id"]
        response = self.client.post(f"/api/v1/conversations/{conversation_id}/messages", json={"content": "Muraho"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["assistant_message"]["content"], "EVA test response: Muraho")

    def test_cross_user_conversation_is_hidden(self):
        item = record(user_id=OTHER_USER_ID, title="Private", language="en")
        self.service.repository.conversations[item.id] = item
        response = self.client.get(f"/api/v1/conversations/{item.id}")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "conversation_not_found")

    def test_stream_uses_sse_contract(self):
        item = record(user_id=USER_ID, title="Stream", language="en")
        self.service.repository.conversations[item.id] = item
        response = self.client.post(f"/api/v1/conversations/{item.id}/messages/stream", json={"content": "Hello"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("event: delta", response.text)
        self.assertIn("event: done", response.text)
