"""Version 1 route registration."""

from fastapi import APIRouter

from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.chat import router as chat_router
from app.api.v1.endpoints.translations import router as translation_router

router = APIRouter()
router.include_router(health_router, prefix="/health", tags=["health"])
router.include_router(chat_router, prefix="/conversations", tags=["conversations"])
router.include_router(translation_router, prefix="/translations", tags=["translations"])
