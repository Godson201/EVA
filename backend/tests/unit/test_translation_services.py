import unittest
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

from app.core.errors import AppError
from app.schemas.translation import TranslationMode
from app.services.language_detection_service import LanguageDetectionService
from app.services.translation_service import TranslationService, split_translation_text


class LanguageDetectionTests(unittest.TestCase):
    def setUp(self):
        self.detector = LanguageDetectionService()

    def test_detects_kinyarwanda(self):
        language, confidence = self.detector.detect("Muraho, ndashaka gusobanura iyi nyandiko yacu")
        self.assertEqual(language, "rw")
        self.assertGreater(confidence, 0.5)

    def test_detects_english(self):
        language, confidence = self.detector.detect("Hello, please explain this document to your student")
        self.assertEqual(language, "en")
        self.assertGreater(confidence, 0.5)

    def test_ambiguous_input_has_honest_low_confidence(self):
        language, confidence = self.detector.detect("EVA")
        self.assertEqual(language, "en")
        self.assertLess(confidence, 0.5)


class TranslationChunkingTests(unittest.TestCase):
    def test_chunks_long_text_without_losing_content(self):
        text = "word " * 700
        chunks = split_translation_text(text, max_chars=200)
        self.assertGreater(len(chunks), 1)
        self.assertEqual(" ".join(" ".join(chunks).split()), " ".join(text.split()))


class FakeSession:
    async def commit(self): pass
    async def refresh(self, item): pass


class FakeRepository:
    async def create(self, **values):
        return SimpleNamespace(id=uuid.uuid4(), created_at=datetime.now(UTC), **values)


class FakeBaseTranslator:
    def __init__(self): self.calls = 0
    async def translate(self, text, source, target):
        self.calls += 1
        return "base translation"


class FakeLLM:
    def __init__(self, fail=False): self.fail = fail
    async def complete(self, messages):
        if self.fail:
            raise AppError("provider", "failed", status_code=502)
        return "styled translation"


class TranslationServiceTests(unittest.IsolatedAsyncioTestCase):
    def make_service(self, llm=None):
        base = FakeBaseTranslator()
        service = TranslationService(FakeSession(), base, llm=llm)
        service.repository = FakeRepository()
        return service, base

    async def test_direct_mode_uses_translation_model(self):
        service, base = self.make_service(FakeLLM())
        item, detected, fallback = await service.translate(
            uuid.uuid4(), "Hello", "rw", TranslationMode.DIRECT, "en"
        )
        self.assertEqual(item.translated_text, "base translation")
        self.assertEqual(base.calls, 1)
        self.assertFalse(detected)
        self.assertFalse(fallback)

    async def test_styled_mode_uses_llm(self):
        service, base = self.make_service(FakeLLM())
        item, _, fallback = await service.translate(
            uuid.uuid4(), "Hello", "rw", TranslationMode.PROFESSIONAL, "en"
        )
        self.assertEqual(item.translated_text, "styled translation")
        self.assertEqual(base.calls, 0)
        self.assertFalse(fallback)

    async def test_styled_mode_falls_back_to_nllb(self):
        service, base = self.make_service(FakeLLM(fail=True))
        item, _, fallback = await service.translate(
            uuid.uuid4(), "Hello", "rw", TranslationMode.ACADEMIC, "en"
        )
        self.assertEqual(item.translated_text, "base translation")
        self.assertEqual(base.calls, 1)
        self.assertTrue(fallback)
