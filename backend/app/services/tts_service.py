from __future__ import annotations

import asyncio
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

from app.core.errors import AppError

EDGE_VOICES = {"en": "en-US-AriaNeural", "rw": "sw-TZ-RehemaNeural"}


@dataclass
class TTSResult:
    content: bytes
    content_type: str
    engine: str
    extension: str


class EdgeTTSEngine:
    async def synthesize(self, text: str, language: str) -> TTSResult:
        import edge_tts
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as handle:
            path = Path(handle.name)
        try:
            await edge_tts.Communicate(text, EDGE_VOICES[language]).save(str(path))
            return TTSResult(await asyncio.to_thread(path.read_bytes), "audio/mpeg", "edge_tts" if language == "en" else "edge_tts_swahili_fallback", "mp3")
        finally:
            path.unlink(missing_ok=True)


class GTTSEngine:
    def _synthesize(self, text, language):
        from gtts import gTTS
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as handle:
            path = Path(handle.name)
        try:
            gTTS(text=text, lang="en" if language == "en" else "sw").save(str(path))
            return TTSResult(path.read_bytes(), "audio/mpeg", "gtts" if language == "en" else "gtts_swahili_fallback", "mp3")
        finally:
            path.unlink(missing_ok=True)

    async def synthesize(self, text, language):
        return await asyncio.to_thread(self._synthesize, text, language)


class XTTSEngine:
    _model = None
    _lock = threading.Lock()

    def _synthesize(self, text, language, sample):
        from TTS.api import TTS
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as sample_handle:
            sample_path = Path(sample_handle.name)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as output_handle:
            output_path = Path(output_handle.name)
        try:
            sample_path.write_bytes(sample)
            with self._lock:
                if self.__class__._model is None:
                    self.__class__._model = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
                self.__class__._model.tts_to_file(text=text, speaker_wav=str(sample_path), language="en", file_path=str(output_path))
            return TTSResult(output_path.read_bytes(), "audio/wav", "xtts_v2", "wav")
        finally:
            sample_path.unlink(missing_ok=True)
            output_path.unlink(missing_ok=True)

    async def synthesize(self, text, language, sample):
        return await asyncio.to_thread(self._synthesize, text, language, sample)


class UnifiedTTSService:
    def __init__(self):
        self.edge, self.gtts, self.xtts = EdgeTTSEngine(), GTTSEngine(), XTTSEngine()

    async def synthesize(self, text: str, language: str, voice_sample: bytes | None = None) -> TTSResult:
        if language not in {"en", "rw"}:
            raise AppError("unsupported_tts_language", "TTS supports English and Kinyarwanda", status_code=422)
        if not text.strip() or len(text) > 20_000:
            raise AppError("invalid_tts_text", "TTS text must contain 1 to 20,000 characters", status_code=422)
        failures = []
        if voice_sample:
            try:
                return await self.xtts.synthesize(text, language, voice_sample)
            except Exception as exc:
                failures.append(f"xtts: {type(exc).__name__}")
        for engine in (self.edge, self.gtts):
            try:
                return await engine.synthesize(text, language)
            except Exception as exc:
                failures.append(f"{engine.__class__.__name__}: {type(exc).__name__}")
        raise AppError("tts_unavailable", "No text-to-speech engine is currently available", status_code=503, details={"engines": failures})
