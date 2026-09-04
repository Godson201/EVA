from __future__ import annotations

import asyncio
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import get_settings
from app.db.session import close_database, initialize_database
from app.models import Attachment, Document, ProcessingJob
from app.repositories.documents import DocumentRepository
from app.services.document_service import DocumentService
from app.services.embedding_service import HuggingFaceEmbeddingService
from app.services.storage_service import build_storage_service
from app.worker import celery_app


async def _process(job_id: str) -> dict:
    settings = get_settings()
    engine = initialize_database(settings)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        job = await session.get(ProcessingJob, uuid.UUID(job_id))
        if job is None or job.document_id is None:
            raise ValueError("Document processing job not found")
        document = await session.get(Document, job.document_id)
        attachment = await session.get(Attachment, document.attachment_id) if document else None
        if document is None or attachment is None:
            raise ValueError("Document or attachment not found")
        job.status, job.progress, job.attempts = "processing", 10, job.attempts + 1
        document.status = "processing"
        await session.commit()
        try:
            content = await build_storage_service(settings).get(attachment.object_key)
            extractor = DocumentService()
            extracted = await extractor.extract(content, document.document_type)
            cleaned = extractor.clean(extracted.text)
            chunks = extractor.chunk(cleaned)
            if not chunks:
                raise ValueError("No readable text was extracted")
            embeddings = await HuggingFaceEmbeddingService(settings).embed([chunk.content for chunk in chunks], "passage")
            await DocumentRepository(session).replace_chunks(document.id, chunks, embeddings)
            document.extracted_text, document.word_count, document.page_count = cleaned, len(cleaned.split()), extracted.page_count
            document.status, document.error_message = "ready", None
            job.status, job.progress, job.result = "completed", 100, {"chunks": len(chunks), "words": document.word_count}
            await session.commit()
            return job.result
        except Exception as exc:
            document.status, document.error_message = "failed", str(exc)[:2000]
            job.status, job.error_message = "failed", str(exc)[:2000]
            await session.commit()
            raise
        finally:
            await close_database()


@celery_app.task(name="documents.process", bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def process_document(self, job_id: str):
    return asyncio.run(_process(job_id))
