from __future__ import annotations

import asyncio
import io
import uuid
from datetime import UTC, datetime

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError
from app.models import Attachment, VoiceProfile
from app.services.audio_preprocessing_service import AudioPreprocessingService


class VoiceQualityService:
    def __init__(self, settings: Settings): self.settings = settings

    def analyze_samples(self, audio, rate: int) -> dict:
        duration = len(audio) / rate
        rms = float(np.sqrt(np.mean(np.square(audio)))) if len(audio) else 0.0
        clipping_ratio = float(np.mean(np.abs(audio) >= 0.99)) if len(audio) else 1.0
        silence_ratio = float(np.mean(np.abs(audio) < 0.01)) if len(audio) else 1.0
        if duration < self.settings.voice_sample_min_seconds or duration > self.settings.voice_sample_max_seconds:
            raise AppError("invalid_voice_duration", f"Voice samples must be {self.settings.voice_sample_min_seconds:g}–{self.settings.voice_sample_max_seconds:g} seconds", status_code=422)
        if rms < 0.01: raise AppError("voice_sample_too_quiet", "Voice sample is too quiet", status_code=422)
        if clipping_ratio > 0.08: raise AppError("voice_sample_clipping", "Voice sample has too much clipping", status_code=422)
        if silence_ratio > 0.65: raise AppError("voice_sample_too_silent", "Voice sample contains too much silence", status_code=422)
        return {"duration_seconds": round(duration, 2), "sample_rate": rate, "rms": round(rms, 5),
                "clipping_ratio": round(clipping_ratio, 5), "silence_ratio": round(silence_ratio, 5),
                "speaker_check": "owner_attested_single_speaker", "quality_passed": True}

    async def analyze(self, content: bytes, suffix: str) -> dict:
        audio, rate = await AudioPreprocessingService().load(content, suffix)
        return self.analyze_samples(audio, rate)

    def prepare_samples(self, audio, rate: int, trim_seconds: float = 50.0):
        original_duration = len(audio) / rate
        limit = min(trim_seconds, self.settings.voice_sample_max_seconds)
        auto_trimmed = original_duration > limit
        if auto_trimmed:
            audio = audio[:int(rate * limit)]
        quality = self.analyze_samples(audio, rate)
        quality.update({"original_duration_seconds": round(original_duration, 2), "auto_trimmed": auto_trimmed})
        return audio, quality

    @staticmethod
    def _wav_bytes(audio, rate: int) -> bytes:
        import soundfile as sf
        buffer = io.BytesIO()
        sf.write(buffer, audio, rate, format="WAV", subtype="PCM_16")
        return buffer.getvalue()

    async def prepare(self, content: bytes, suffix: str):
        audio, rate = await AudioPreprocessingService().load(content, suffix)
        prepared, quality = self.prepare_samples(audio, rate)
        if not quality["auto_trimmed"]:
            return content, suffix, quality
        normalized = await asyncio.to_thread(self._wav_bytes, prepared, rate)
        return normalized, "wav", quality


class VoiceProfileService:
    def __init__(self, session: AsyncSession, settings: Settings, storage):
        self.session, self.settings, self.storage = session, settings, storage

    async def get_owned(self, profile_id, user_id):
        return await self.session.scalar(select(VoiceProfile).where(VoiceProfile.id == profile_id, VoiceProfile.user_id == user_id))

    async def require_owned(self, profile_id, user_id):
        profile = await self.get_owned(profile_id, user_id)
        if profile is None: raise AppError("voice_profile_not_found", "Voice profile not found", status_code=404)
        return profile

    async def list_owned(self, user_id, offset, limit):
        total = await self.session.scalar(select(func.count()).select_from(VoiceProfile).where(VoiceProfile.user_id == user_id)) or 0
        rows = await self.session.scalars(select(VoiceProfile).where(VoiceProfile.user_id == user_id).order_by(VoiceProfile.created_at.desc()).offset(offset).limit(limit))
        return list(rows), total

    async def create(self, user_id, name, language, purpose, assertion, quality, attachment_values):
        attachment = Attachment(user_id=user_id, **attachment_values); self.session.add(attachment); await self.session.flush()
        profile = VoiceProfile(user_id=user_id, attachment_id=attachment.id, name=name, language=language, status="active",
                               consent_version=self.settings.voice_consent_version, consent_assertion=assertion, purpose=purpose,
                               consented_at=datetime.now(UTC), quality_metadata=quality)
        self.session.add(profile); await self.session.flush(); return profile

    async def revoke(self, profile_id, user_id):
        profile = await self.require_owned(profile_id, user_id)
        if profile.status == "revoked": return profile
        profile.status, profile.revoked_at = "revoked", datetime.now(UTC)
        await self.session.flush(); return profile

    async def export(self, profile_id, user_id):
        profile = await self.require_owned(profile_id, user_id)
        attachment = await self.session.get(Attachment, profile.attachment_id)
        if attachment is None or attachment.user_id != user_id: raise AppError("voice_sample_not_found", "Voice sample not found", status_code=404)
        return profile, attachment, await self.storage.get_private(attachment.object_key)

    async def delete(self, profile_id, user_id):
        profile = await self.require_owned(profile_id, user_id)
        attachment = await self.session.get(Attachment, profile.attachment_id)
        profile.status, profile.deletion_requested_at = "deleting", datetime.now(UTC)
        await self.session.flush()
        if attachment:
            await self.storage.delete(attachment.object_key)
        await self.session.delete(profile)
        if attachment: await self.session.delete(attachment)
