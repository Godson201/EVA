"""Version 1 route registration."""

from fastapi import APIRouter

from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.chat import router as chat_router
from app.api.v1.endpoints.translations import router as translation_router
from app.api.v1.endpoints.documents import router as document_router
from app.api.v1.endpoints.speech import router as speech_router

router = APIRouter()
router.include_router(health_router, prefix="/health", tags=["health"])
router.include_router(chat_router, prefix="/conversations", tags=["conversations"])
router.include_router(translation_router, prefix="/translations", tags=["translations"])
router.include_router(document_router, prefix="/documents", tags=["documents"])
router.include_router(speech_router, prefix="/speech", tags=["speech"])
