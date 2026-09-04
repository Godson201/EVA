from __future__ import annotations

from celery import Celery
import asyncio

from app.core.config import Settings


def create_celery_app(settings: Settings) -> Celery:
    app = Celery("eva", broker=settings.redis_url, backend=settings.redis_url, include=["app.tasks.documents", "app.tasks.speech"])
    app.conf.update(
        task_serializer="json", result_serializer="json", accept_content=["json"],
        task_track_started=True, task_acks_late=True,
        task_routes={"documents.process": {"queue": "documents"}, "speech.transcribe": {"queue": "speech"}, "speech.synthesize": {"queue": "speech"}},
    )
    return app


class CeleryJobService:
    def __init__(self, celery_app: Celery):
        self.app = celery_app

    async def enqueue(self, task: str, payload: dict) -> str:
        result = await asyncio.to_thread(self.app.send_task, task, kwargs=payload)
        return result.id

    async def status(self, job_id: str) -> dict:
        result = await asyncio.to_thread(self.app.AsyncResult, job_id)
        return {"id": job_id, "status": result.status, "result": result.result if result.ready() else None}
