from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentUser, get_current_user
from app.core.errors import AppError
from app.db.session import get_session
from app.schemas.study import StudyArtifactList, StudyArtifactRead, StudyGenerate, StudyType
from app.services.embedding_service import HuggingFaceEmbeddingService
from app.services.llm_service import build_llm_service
from app.services.study_service import StudyService

router = APIRouter()


def get_study_service(request: Request, session: AsyncSession = Depends(get_session)):
    settings = request.app.state.settings
    return StudyService(session, build_llm_service(settings), HuggingFaceEmbeddingService(settings))


@router.post("/generate", response_model=StudyArtifactRead, status_code=201)
async def generate_study_artifact(payload: StudyGenerate, user: CurrentUser = Depends(get_current_user),
                                  service: StudyService = Depends(get_study_service)):
    return await service.generate(user.id, payload)


@router.get("/artifacts", response_model=StudyArtifactList)
async def list_study_artifacts(artifact_type: StudyType | None = None, offset: int = Query(default=0, ge=0),
                               limit: int = Query(default=20, ge=1, le=100), user: CurrentUser = Depends(get_current_user),
                               service: StudyService = Depends(get_study_service)):
    items, total = await service.repository.list_owned(user.id, artifact_type, offset, limit)
    return StudyArtifactList(items=items, total=total)


@router.get("/artifacts/{artifact_id}", response_model=StudyArtifactRead)
async def get_study_artifact(artifact_id: uuid.UUID, user: CurrentUser = Depends(get_current_user),
                             service: StudyService = Depends(get_study_service)):
    artifact = await service.repository.get_owned(artifact_id, user.id)
    if artifact is None: raise AppError("study_artifact_not_found", "Study artifact not found", status_code=404)
    return artifact


@router.delete("/artifacts/{artifact_id}", status_code=204)
async def delete_study_artifact(artifact_id: uuid.UUID, user: CurrentUser = Depends(get_current_user),
                                service: StudyService = Depends(get_study_service)):
    artifact = await service.repository.get_owned(artifact_id, user.id)
    if artifact is None: raise AppError("study_artifact_not_found", "Study artifact not found", status_code=404)
    await service.repository.delete(artifact); await service.session.commit()
