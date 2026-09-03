from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
import unittest

from fastapi.testclient import TestClient

from app.api.dependencies import CurrentUser, get_current_user
from app.api.v1.endpoints.translations import get_translation_service
from app.core.config import Settings
from app.main import create_app

USER_ID = uuid.uuid4()


class FakeRepository:
    async def list_owned(self, user_id, offset, limit):
        return [], 0


class FakeTranslationService:
    def __init__(self):
        self.repository = FakeRepository()

    async def translate(self, user_id, text, target, mode, source=None, conversation_id=None):
        detected = source is None
        source = source or ("rw" if "Muraho" in text else "en")
        now = datetime.now(UTC)
        item = SimpleNamespace(
            id=uuid.uuid4(), source_text=text, translated_text="Hello" if target == "en" else "Muraho",
            source_language=source, target_language=target, mode=mode.value,
            provider="fake", created_at=now,
        )
        return item, detected, False


class TranslationApiTests(unittest.TestCase):
    def setUp(self):
        app = create_app(Settings(environment="test", _env_file=None), include_legacy=False)
        self.service = FakeTranslationService()
        app.dependency_overrides[get_current_user] = lambda: CurrentUser(USER_ID, "USER")
        app.dependency_overrides[get_translation_service] = lambda: self.service
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()

    def test_automatic_language_translation(self):
        response = self.client.post("/api/v1/translations", json={
            "text": "Muraho", "target_language": "en", "mode": "natural",
        })
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()["detected_automatically"])
        self.assertEqual(response.json()["translation"]["translated_text"], "Hello")

    def test_all_modes_are_accepted(self):
        for mode in ("direct", "natural", "simple", "professional", "academic", "call-center"):
            response = self.client.post("/api/v1/translations", json={
                "text": "Hello", "source_language": "en", "target_language": "rw", "mode": mode,
            })
            self.assertEqual(response.status_code, 201, mode)

    def test_same_explicit_languages_are_rejected(self):
        response = self.client.post("/api/v1/translations", json={
            "text": "Hello", "source_language": "en", "target_language": "en",
        })
        self.assertEqual(response.status_code, 422)

    def test_legacy_adapter_preserves_response_shape(self):
        response = self.client.post("/api/translate", json={
            "text": "Hello", "source_lang": "en", "target_lang": "rw", "mode": "direct",
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertEqual(response.json()["translated_text"], "Muraho")
