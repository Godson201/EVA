from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentUser, get_current_user
from app.db.session import get_session
from app.schemas.translation import LegacyTranslationRequest, TranslationCreate, TranslationList, TranslationResult
from app.services.llm_service import build_llm_service
from app.services.translation_service import NLLBTranslationService, TranslationService

router = APIRouter()
compatibility_router = APIRouter()


def get_translation_service(request: Request, session: AsyncSession = Depends(get_session)) -> TranslationService:
    settings = request.app.state.settings
    return TranslationService(session, NLLBTranslationService(settings), build_llm_service(settings))


@router.post("", response_model=TranslationResult, status_code=201)
async def create_translation(payload: TranslationCreate, user: CurrentUser = Depends(get_current_user), service: TranslationService = Depends(get_translation_service)):
    item, detected, fallback = await service.translate(
        user.id, payload.text.strip(), payload.target_language, payload.mode,
        payload.source_language, payload.conversation_id,
    )
    return TranslationResult(translation=item, detected_automatically=detected, fallback_used=fallback)


@router.get("", response_model=TranslationList)
async def list_translations(
    offset: int = Query(default=0, ge=0), limit: int = Query(default=20, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user), service: TranslationService = Depends(get_translation_service),
):
    items, total = await service.repository.list_owned(user.id, offset, limit)
    return TranslationList(items=items, total=total)


@compatibility_router.post("/api/translate")
async def legacy_translate(payload: LegacyTranslationRequest, user: CurrentUser = Depends(get_current_user), service: TranslationService = Depends(get_translation_service)):
    item, detected, fallback = await service.translate(
        user.id, payload.text.strip(), payload.target_lang, payload.mode, payload.source_lang,
    )
    return {
        "success": True, "translated_text": item.translated_text,
        "source_lang": item.source_language, "target_lang": item.target_language,
        "mode": item.mode, "detected_automatically": detected, "fallback_used": fallback,
    }
