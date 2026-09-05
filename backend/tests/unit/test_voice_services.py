import asyncio
import tempfile
import uuid
from pathlib import Path

import numpy as np
import pytest

from app.core.config import Settings
from app.core.errors import AppError
from app.services.storage_service import LocalStorageService
from app.services.voice_service import VoiceProfileService, VoiceQualityService


def test_private_storage_encrypts_voice_bytes_at_rest():
    with tempfile.TemporaryDirectory() as directory:
        service = LocalStorageService(directory, "test-encryption-key")
        asyncio.run(service.put_private("users/u/voices/sample.enc", b"recognizable voice bytes", "audio/wav"))
        stored = Path(directory, "users/u/voices/sample.enc").read_bytes()
        assert b"recognizable voice bytes" not in stored
        assert asyncio.run(service.get_private("users/u/voices/sample.enc")) == b"recognizable voice bytes"


def test_voice_quality_accepts_clear_bounded_sample():
    settings = Settings(environment="test", voice_sample_min_seconds=5, voice_sample_max_seconds=60, _env_file=None)
    audio = np.tile(np.array([0.15, -0.15, 0.08, -0.08], dtype=np.float32), 20_000)
    result = VoiceQualityService(settings).analyze_samples(audio, 16_000)
    assert result["quality_passed"] is True
    assert result["speaker_check"] == "owner_attested_single_speaker"


def test_voice_quality_rejects_short_and_clipped_samples():
    service = VoiceQualityService(Settings(environment="test", _env_file=None))
    with pytest.raises(AppError) as short:
        service.analyze_samples(np.ones(16_000, dtype=np.float32) * .2, 16_000)
    assert short.value.code == "invalid_voice_duration"
    with pytest.raises(AppError) as clipped:
        service.analyze_samples(np.ones(16_000 * 6, dtype=np.float32), 16_000)
    assert clipped.value.code == "voice_sample_clipping"


def test_long_voice_sample_is_automatically_trimmed_to_50_seconds():
    settings = Settings(environment="test", voice_sample_min_seconds=5, voice_sample_max_seconds=60, _env_file=None)
    service = VoiceQualityService(settings)
    audio = np.tile(np.array([0.15, -0.15, 0.08, -0.08], dtype=np.float32), 16_000 * 18)
    prepared, quality = service.prepare_samples(audio, 16_000)
    assert len(prepared) == 16_000 * 50
    assert quality["duration_seconds"] == 50
    assert quality["original_duration_seconds"] == 72
    assert quality["auto_trimmed"] is True


class MissingSession:
    async def scalar(self, query): return None


def test_cross_user_voice_profile_is_hidden():
    service = VoiceProfileService(MissingSession(), Settings(environment="test", _env_file=None), object())
    with pytest.raises(AppError) as error:
        asyncio.run(service.require_owned(uuid.uuid4(), uuid.uuid4()))
    assert error.value.code == "voice_profile_not_found"
