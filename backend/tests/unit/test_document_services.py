import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from app.core.errors import AppError
from app.services.document_service import DocumentService
from app.services.storage_service import LocalStorageService


class DocumentServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.service = DocumentService()

    async def test_extracts_and_chunks_utf8_text(self):
        extracted = await self.service.extract("Muraho\n\nHello".encode(), "txt")
        chunks = self.service.chunk(self.service.clean(extracted.text), target_chars=20, overlap_chars=3)
        self.assertTrue(chunks)
        self.assertIn("Muraho", chunks[0].content)

    def test_rejects_mime_extension_mismatch(self):
        with self.assertRaises(AppError):
            self.service.validate("notes.pdf", "text/plain", b"notes", 1000)

    def test_rejects_oversized_documents(self):
        with self.assertRaises(AppError):
            self.service.validate("notes.txt", "text/plain", b"12345", 4)

    def test_reports_missing_tesseract_clearly(self):
        import pytesseract
        from PIL import Image

        with patch.object(pytesseract, "image_to_string", side_effect=pytesseract.TesseractNotFoundError()):
            with self.assertRaisesRegex(RuntimeError, "Install Tesseract OCR"):
                self.service._ocr_image(Image.new("RGB", (10, 10), "white"))

    def test_whisper_generation_limit_leaves_prompt_space(self):
        from app.services.transcription_service import WhisperTranscriptionService

        model = type("Model", (), {"config": type("Config", (), {"max_target_positions": 448})()})()
        self.assertLessEqual(WhisperTranscriptionService._max_new_tokens(model) + 4, 448)


class LocalStorageTests(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_and_delete(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = LocalStorageService(directory)
            await storage.put("users/one/document.txt", b"EVA", "text/plain")
            self.assertEqual(await storage.get("users/one/document.txt"), b"EVA")
            await storage.delete("users/one/document.txt")
            self.assertFalse((Path(directory) / "users/one/document.txt").exists())

    async def test_path_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = LocalStorageService(directory)
            with self.assertRaises(AppError):
                await storage.put("../escape.txt", b"bad", "text/plain")
