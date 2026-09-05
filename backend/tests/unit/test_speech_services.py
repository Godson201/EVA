import asyncio
import sys

import pytest

from app.core.config import Settings
from app.core.errors import AppError
from app.services.audio_preprocessing_service import AudioPreprocessingService
from app.services.transcription_service import WhisperTranscriptionService
from app.services.tts_service import TTSResult, UnifiedTTSService


@pytest.mark.parametrize(("filename", "content_type", "content", "expected"), [
    ("sample.wav", "audio/wav", b"RIFF" + b"\0" * 20, "wav"),
    ("sample.mp3", "audio/mpeg", b"ID3" + b"\0" * 20, "mp3"),
    ("sample.ogg", "audio/ogg", b"OggS" + b"\0" * 20, "ogg"),
    ("sample.webm", "audio/webm", b"\x1aE\xdf\xa3" + b"\0" * 20, "webm"),
    ("sample.m4a", "audio/mp4", b"\0\0\0\x18ftypM4A " + b"\0" * 8, "m4a"),
])
def test_audio_validation(filename, content_type, content, expected):
    assert AudioPreprocessingService().validate(filename, content_type, content, 100) == expected


def test_audio_validation_rejects_mismatch_and_oversize():
    service = AudioPreprocessingService()
    with pytest.raises(AppError) as mismatch:
        service.validate("sample.wav", "audio/mpeg", b"ID3data", 100)
    assert mismatch.value.code == "audio_type_mismatch"
    with pytest.raises(AppError) as oversize:
        service.validate("sample.wav", "audio/wav", b"RIFFdata", 4)
    assert oversize.value.code == "invalid_audio_size"


def test_transcription_dependencies_are_lazy():
    sys.modules.pop("transformers", None)
    WhisperTranscriptionService(Settings())
    assert "transformers" not in sys.modules


def test_tts_falls_back_to_second_engine():
    calls = []

    class Failing:
        async def synthesize(self, text, language):
            calls.append("first")
            raise RuntimeError("offline")

    class Working:
        async def synthesize(self, text, language):
            calls.append("second")
            return TTSResult(b"audio", "audio/mpeg", "fake", "mp3")

    service = UnifiedTTSService()
    service.edge, service.gtts = Failing(), Working()
    result = asyncio.run(service.synthesize("Hello", "en"))
    assert result.engine == "fake"
    assert calls == ["first", "second"]


def test_tts_does_not_block_on_unaccepted_xtts_license():
    class Working:
        async def synthesize(self, text, language):
            return TTSResult(b"audio", "audio/mpeg", "default", "mp3")

    service = UnifiedTTSService(coqui_tos_agreed=False)
    service.edge = Working()
    result = asyncio.run(service.synthesize("Read my notes", "en", b"voice sample"))
    assert result.engine == "default"


def test_tts_rejects_invalid_input():
    with pytest.raises(AppError):
        asyncio.run(UnifiedTTSService().synthesize("", "en"))
    with pytest.raises(AppError):
        asyncio.run(UnifiedTTSService().synthesize("Hello", "fr"))
