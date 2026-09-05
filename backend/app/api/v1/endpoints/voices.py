from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentUser, get_current_user
from app.core.errors import AppError
from app.db.session import get_session
from app.schemas.voice import VoiceConsentDisclosure, VoiceProfileList, VoiceProfileRead
from app.services.audio_preprocessing_service import AudioPreprocessingService
from app.services.storage_service import build_storage_service
from app.services.voice_service import VoiceProfileService, VoiceQualityService

router = APIRouter()


def _service(request, session): return VoiceProfileService(session, request.app.state.settings, build_storage_service(request.app.state.settings))


@router.get("/consent", response_model=VoiceConsentDisclosure)
async def consent_disclosure(request: Request):
    return VoiceConsentDisclosure(version=request.app.state.settings.voice_consent_version, title="Consent to create a personal EVA voice",
        risks=["A cloned voice can sound like the recorded speaker.", "Generated speech could be misunderstood as authentic.", "Your reference recording is encrypted and retained until you delete it."],
        required_assertions=["The voice is mine or I have explicit authorization.", "Only one consenting speaker is present.", "I will use the profile only for lawful, non-deceptive purposes."])


@router.post("", response_model=VoiceProfileRead, status_code=201)
async def create_voice_profile(request: Request, file: UploadFile = File(...), name: str = Form(min_length=1, max_length=100),
    language: str = Form(pattern="^(en|rw)$"), purpose: str = Form(min_length=3, max_length=255),
    consent_version: str = Form(), ownership_confirmed: bool = Form(), single_speaker_confirmed: bool = Form(),
    responsible_use_confirmed: bool = Form(), user: CurrentUser = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    settings = request.app.state.settings
    if consent_version != settings.voice_consent_version: raise AppError("outdated_voice_consent", "Review and accept the current voice consent disclosure", status_code=409)
    if not all((ownership_confirmed, single_speaker_confirmed, responsible_use_confirmed)):
        raise AppError("voice_consent_required", "All voice ownership and responsible-use assertions are required", status_code=422)
    content = await file.read(settings.max_audio_bytes + 1); content_type = file.content_type or "application/octet-stream"
    filename = Path(file.filename or "voice.wav").name
    audio_type = AudioPreprocessingService().validate(filename, content_type, content, settings.max_audio_bytes)
    content, prepared_type, quality = await VoiceQualityService(settings).prepare(content, audio_type)
    if prepared_type == "wav" and audio_type != "wav":
        filename = f"{Path(filename).stem}-50s.wav"
        content_type = "audio/wav"
    object_key = f"users/{user.id}/voices/{uuid.uuid4()}/{filename}.enc"; storage = build_storage_service(settings)
    await storage.put_private(object_key, content, content_type)
    try:
        assertion = "I confirm ownership or authorization, a single consenting speaker, and lawful non-deceptive use."
        profile = await _service(request, session).create(user.id, name.strip(), language, purpose.strip(), assertion, quality,
            {"object_key": object_key, "original_filename": filename, "content_type": content_type, "size_bytes": len(content), "checksum_sha256": hashlib.sha256(content).hexdigest()})
        await session.commit(); await session.refresh(profile); return profile
    except Exception:
        await session.rollback(); await storage.delete(object_key); raise


@router.get("", response_model=VoiceProfileList)
async def list_voice_profiles(request: Request, offset: int = Query(default=0, ge=0), limit: int = Query(default=20, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    items, total = await _service(request, session).list_owned(user.id, offset, limit); return VoiceProfileList(items=items, total=total)


@router.post("/{profile_id}/revoke", response_model=VoiceProfileRead)
async def revoke_voice_profile(profile_id: uuid.UUID, request: Request, user: CurrentUser = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    profile = await _service(request, session).revoke(profile_id, user.id); await session.commit(); await session.refresh(profile); return profile


@router.get("/{profile_id}/export")
async def export_voice_profile(profile_id: uuid.UUID, request: Request, user: CurrentUser = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    _, attachment, content = await _service(request, session).export(profile_id, user.id)
    filename = attachment.original_filename.replace('"', "")
    return Response(content=content, media_type=attachment.content_type, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.delete("/{profile_id}", status_code=204)
async def delete_voice_profile(profile_id: uuid.UUID, request: Request, user: CurrentUser = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    await _service(request, session).delete(profile_id, user.id); await session.commit()
