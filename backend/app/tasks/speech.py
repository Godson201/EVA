from __future__ import annotations

import asyncio
import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import get_settings
from app.db.session import close_database, initialize_database
from app.models import Attachment, ProcessingJob, Transcription
from app.repositories.speech import SpeechRepository
from app.services.storage_service import build_storage_service
from app.services.transcription_service import WhisperTranscriptionService
from app.services.tts_service import UnifiedTTSService
from app.worker import celery_app


async def _transcribe(job_id: str, language: str, audio_type: str) -> dict:
    settings = get_settings()
    engine = initialize_database(settings)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            job = await session.get(ProcessingJob, uuid.UUID(job_id))
            transcription = await session.get(Transcription, job.transcription_id) if job and job.transcription_id else None
            attachment = await session.get(Attachment, job.attachment_id) if job and job.attachment_id else None
            if job is None or transcription is None or attachment is None:
                raise ValueError("Transcription processing job not found")
            job.status, job.progress, job.attempts = "processing", 10, job.attempts + 1
            transcription.status = "processing"
            await session.commit()
            try:
                content = await build_storage_service(settings).get(attachment.object_key)
                result = await WhisperTranscriptionService(settings).transcribe(content, audio_type, language)
                transcription.raw_text = result.raw_text
                transcription.corrected_text = result.corrected_text
                transcription.language = result.language
                transcription.duration_seconds = result.duration_seconds
                transcription.timestamps = result.timestamps
                transcription.model = result.model
                transcription.status = "completed"
                job.status, job.progress = "completed", 100
                job.result = {"transcription_id": str(transcription.id), "language": result.language, "duration_seconds": result.duration_seconds}
                await session.commit()
                return job.result
            except Exception as exc:
                transcription.status = "failed"
                job.status, job.error_message = "failed", str(exc)[:2000]
                await session.commit()
                raise
    finally:
        await close_database()


async def _synthesize(job_id: str, text: str, language: str, voice_profile_id: str | None = None) -> dict:
    settings = get_settings()
    engine = initialize_database(settings)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            job = await session.get(ProcessingJob, uuid.UUID(job_id))
            if job is None:
                raise ValueError("Speech synthesis job not found")
            job.status, job.progress, job.attempts = "processing", 10, job.attempts + 1
            await session.commit()
            try:
                storage = build_storage_service(settings)
                sample = None
                if voice_profile_id:
                    owned = await SpeechRepository(session).voice_sample(uuid.UUID(voice_profile_id), job.user_id)
                    if owned is None:
                        raise ValueError("Active, consented voice profile not found")
                    _, sample_attachment = owned
                    sample = await storage.get_private(sample_attachment.object_key)
                result = await UnifiedTTSService().synthesize(text, language, sample)
                object_key = f"users/{job.user_id}/speech/generated/{uuid.uuid4()}.{result.extension}"
                await storage.put(object_key, result.content, result.content_type)
                attachment = Attachment(
                    user_id=job.user_id, object_key=object_key, original_filename=f"eva-speech.{result.extension}",
                    content_type=result.content_type, size_bytes=len(result.content),
                )
                session.add(attachment)
                await session.flush()
                job.attachment_id = attachment.id
                job.status, job.progress = "completed", 100
                job.result = {"attachment_id": str(attachment.id), "content_type": result.content_type, "engine": result.engine}
                await session.commit()
                return job.result
            except Exception as exc:
                job.status, job.error_message = "failed", str(exc)[:2000]
                await session.commit()
                raise
    finally:
        await close_database()


@celery_app.task(name="speech.transcribe", bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def transcribe_audio(self, job_id: str, language: str, audio_type: str):
    return asyncio.run(_transcribe(job_id, language, audio_type))


@celery_app.task(name="speech.synthesize", bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def synthesize_speech(self, job_id: str, text: str, language: str, voice_profile_id: str | None = None):
    return asyncio.run(_synthesize(job_id, text, language, voice_profile_id))
