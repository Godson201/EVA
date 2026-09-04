from __future__ import annotations

import uuid
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Attachment, ProcessingJob, Transcription, VoiceProfile


class SpeechRepository:
    def __init__(self, session: AsyncSession): self.session = session

    async def create_transcription_job(self, user_id, object_key, filename, content_type, size, language):
        attachment = Attachment(user_id=user_id, object_key=object_key, original_filename=filename, content_type=content_type, size_bytes=size)
        self.session.add(attachment); await self.session.flush()
        transcription = Transcription(user_id=user_id, attachment_id=attachment.id, source="upload", language=language, status="pending")
        self.session.add(transcription); await self.session.flush()
        job = ProcessingJob(user_id=user_id, attachment_id=attachment.id, transcription_id=transcription.id, task_name="speech.transcribe", status="pending")
        self.session.add(job); await self.session.flush()
        return attachment, transcription, job

    async def create_tts_job(self, user_id):
        job = ProcessingJob(user_id=user_id, task_name="speech.synthesize", status="pending")
        self.session.add(job); await self.session.flush(); return job

    async def get_owned(self, transcription_id, user_id):
        return await self.session.scalar(select(Transcription).where(Transcription.id == transcription_id, Transcription.user_id == user_id))

    async def list_owned(self, user_id, offset, limit):
        total = await self.session.scalar(select(func.count()).select_from(Transcription).where(Transcription.user_id == user_id)) or 0
        rows = await self.session.scalars(select(Transcription).where(Transcription.user_id == user_id).order_by(Transcription.created_at.desc()).offset(offset).limit(limit))
        return list(rows), total

    async def voice_sample(self, voice_id: uuid.UUID, user_id: uuid.UUID):
        result = await self.session.execute(select(VoiceProfile, Attachment).join(Attachment, VoiceProfile.attachment_id == Attachment.id).where(
            VoiceProfile.id == voice_id, VoiceProfile.user_id == user_id,
            VoiceProfile.status == "active", VoiceProfile.consented_at.is_not(None), VoiceProfile.revoked_at.is_(None),
        ))
        return result.first()
