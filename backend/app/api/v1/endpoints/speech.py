from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentUser, get_current_user
from app.core.errors import AppError
from app.db.session import get_session
from app.models import Attachment, ProcessingJob
from app.repositories.speech import SpeechRepository
from app.schemas.speech import SpeechJobRead, SynthesisRequest, SynthesisResult, TranscriptionList, TranscriptionRead, TranscriptionUploadResult
from app.services.audio_preprocessing_service import AudioPreprocessingService
from app.services.job_service import CeleryJobService, create_celery_app
from app.services.storage_service import build_storage_service

router = APIRouter()


@router.post("/transcriptions", response_model=TranscriptionUploadResult, status_code=202)
async def create_transcription(
    request: Request,
    file: UploadFile = File(...),
    language: str = Form(default="auto", pattern="^(auto|en|rw)$"),
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    settings = request.app.state.settings
    content = await file.read(settings.max_audio_bytes + 1)
    content_type = file.content_type or "application/octet-stream"
    safe_filename = Path(file.filename or "audio").name
    audio_type = AudioPreprocessingService().validate(safe_filename, content_type, content, settings.max_audio_bytes)
    object_key = f"users/{user.id}/speech/uploads/{uuid.uuid4()}/{safe_filename}"
    storage = build_storage_service(settings)
    await storage.put(object_key, content, content_type)
    committed = False
    try:
        attachment, transcription, job = await SpeechRepository(session).create_transcription_job(
            user.id, object_key, safe_filename, content_type, len(content), language
        )
        attachment.checksum_sha256 = hashlib.sha256(content).hexdigest()
        await session.commit()
        committed = True
        await session.refresh(transcription)
        try:
            task_id = await CeleryJobService(create_celery_app(settings)).enqueue(
                "speech.transcribe", {"job_id": str(job.id), "language": language, "audio_type": audio_type}
            )
            job.celery_task_id = task_id
            await session.commit()
        except Exception as exc:
            transcription.status = "failed"
            job.status, job.error_message = "failed", "Speech queue is unavailable"
            await session.commit()
            raise AppError("job_queue_unavailable", "Transcription could not be queued", status_code=503) from exc
        return TranscriptionUploadResult(transcription=transcription, job_id=job.id)
    except Exception:
        await session.rollback()
        if not committed:
            await storage.delete(object_key)
        raise


@router.get("/transcriptions", response_model=TranscriptionList)
async def list_transcriptions(
    offset: int = Query(default=0, ge=0), limit: int = Query(default=20, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user), session: AsyncSession = Depends(get_session),
):
    items, total = await SpeechRepository(session).list_owned(user.id, offset, limit)
    return TranscriptionList(items=items, total=total)


@router.get("/transcriptions/{transcription_id}", response_model=TranscriptionRead)
async def get_transcription(
    transcription_id: uuid.UUID, user: CurrentUser = Depends(get_current_user), session: AsyncSession = Depends(get_session),
):
    transcription = await SpeechRepository(session).get_owned(transcription_id, user.id)
    if transcription is None:
        raise AppError("transcription_not_found", "Transcription not found", status_code=404)
    return transcription


@router.post("/synthesize", response_model=SynthesisResult, status_code=202)
async def synthesize(
    payload: SynthesisRequest, request: Request, user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    repository = SpeechRepository(session)
    if payload.voice_profile_id and await repository.voice_sample(payload.voice_profile_id, user.id) is None:
        raise AppError("voice_profile_not_available", "An active, consented voice profile is required", status_code=404)
    job = await repository.create_tts_job(user.id)
    await session.commit()
    try:
        task_id = await CeleryJobService(create_celery_app(request.app.state.settings)).enqueue(
            "speech.synthesize", {"job_id": str(job.id), "text": payload.text, "language": payload.language,
                                  "voice_profile_id": str(payload.voice_profile_id) if payload.voice_profile_id else None}
        )
        job.celery_task_id = task_id
        await session.commit()
    except Exception as exc:
        job.status, job.error_message = "failed", "Speech queue is unavailable"
        await session.commit()
        raise AppError("job_queue_unavailable", "Speech synthesis could not be queued", status_code=503) from exc
    return SynthesisResult(job_id=job.id, status=job.status)


@router.get("/jobs/{job_id}", response_model=SpeechJobRead)
async def get_speech_job(
    job_id: uuid.UUID, user: CurrentUser = Depends(get_current_user), session: AsyncSession = Depends(get_session),
):
    job = await session.scalar(select(ProcessingJob).where(ProcessingJob.id == job_id, ProcessingJob.user_id == user.id,
                                                           ProcessingJob.task_name.in_(("speech.transcribe", "speech.synthesize"))))
    if job is None:
        raise AppError("job_not_found", "Speech job not found", status_code=404)
    return job


@router.get("/attachments/{attachment_id}")
async def download_speech_attachment(
    attachment_id: uuid.UUID, request: Request, user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    attachment = await session.scalar(select(Attachment).where(Attachment.id == attachment_id, Attachment.user_id == user.id))
    if attachment is None:
        raise AppError("attachment_not_found", "Speech attachment not found", status_code=404)
    content = await build_storage_service(request.app.state.settings).get(attachment.object_key)
    filename = attachment.original_filename.replace('"', "")
    return Response(content=content, media_type=attachment.content_type,
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})
