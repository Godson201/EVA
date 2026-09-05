from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentUser, get_current_user
from app.core.errors import AppError
from app.db.session import get_session
from app.repositories.documents import DocumentRepository
from app.schemas.document import DocumentAnswer, DocumentContent, DocumentList, DocumentRead, DocumentSummary, DocumentUploadResult, ProcessingJobRead, QuestionRequest, SearchHit, SearchRequest
from app.services.document_service import DocumentService
from app.services.embedding_service import HuggingFaceEmbeddingService
from app.services.job_service import CeleryJobService, create_celery_app
from app.services.llm_service import build_llm_service
from app.services.storage_service import build_storage_service

router = APIRouter()


def _services(request: Request, session: AsyncSession):
    settings = request.app.state.settings
    return settings, DocumentRepository(session), build_storage_service(settings)


@router.post("", response_model=DocumentUploadResult, status_code=202)
async def upload_document(
    request: Request, file: UploadFile = File(...), user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    settings, repository, storage = _services(request, session)
    content = await file.read(settings.max_document_bytes + 1)
    content_type = file.content_type or "application/octet-stream"
    safe_filename = Path(file.filename or "document").name
    document_type = DocumentService().validate(safe_filename, content_type, content, settings.max_document_bytes)
    digest = hashlib.sha256(content).hexdigest()
    object_key = f"users/{user.id}/documents/{uuid.uuid4()}/{safe_filename}"
    await storage.put(object_key, content, content_type)
    committed = False
    try:
        attachment, document, job = await repository.create_upload(
            user.id, object_key, safe_filename, content_type, len(content), document_type
        )
        attachment.checksum_sha256 = digest
        await session.commit()
        committed = True
        await session.refresh(document)
        try:
            task_id = await CeleryJobService(create_celery_app(settings)).enqueue("documents.process", {"job_id": str(job.id)})
            job.celery_task_id = task_id
            await session.commit()
        except Exception as exc:
            document.status, document.error_message = "failed", "Document queue is unavailable"
            job.status, job.error_message = "failed", "Document queue is unavailable"
            await session.commit()
            raise AppError("job_queue_unavailable", "Document processing could not be queued", status_code=503) from exc
        return DocumentUploadResult(document=document, job_id=job.id)
    except Exception:
        await session.rollback()
        if not committed:
            await storage.delete(object_key)
        raise


@router.get("", response_model=DocumentList)
async def list_documents(
    offset: int = Query(default=0, ge=0), limit: int = Query(default=20, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user), session: AsyncSession = Depends(get_session),
):
    items, total = await DocumentRepository(session).list_owned(user.id, offset, limit)
    return DocumentList(items=items, total=total)


@router.get("/jobs/{job_id}", response_model=ProcessingJobRead)
async def get_processing_job(job_id: uuid.UUID, user: CurrentUser = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    job = await DocumentRepository(session).get_job_owned(job_id, user.id)
    if job is None:
        raise AppError("job_not_found", "Processing job not found", status_code=404)
    return job


async def _search(payload: SearchRequest, user, session, request) -> list[SearchHit]:
    repository = DocumentRepository(session)
    if payload.document_id and await repository.get_owned(payload.document_id, user.id) is None:
        raise AppError("document_not_found", "Document not found", status_code=404)
    embedding = (await HuggingFaceEmbeddingService(request.app.state.settings).embed([payload.query], "query"))[0]
    rows = await repository.search(user.id, embedding, payload.limit, payload.document_id)
    return [SearchHit(
        chunk_id=chunk.id, document_id=chunk.document_id, chunk_index=chunk.chunk_index,
        content=chunk.content, page_number=chunk.page_number, score=max(0.0, 1.0 - float(distance)),
    ) for chunk, distance in rows]


@router.post("/search", response_model=list[SearchHit])
async def semantic_search(payload: SearchRequest, request: Request, user: CurrentUser = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    return await _search(payload, user, session, request)


@router.post("/ask", response_model=DocumentAnswer)
async def ask_documents(payload: QuestionRequest, request: Request, user: CurrentUser = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    sources = await _search(payload, user, session, request)
    if not sources:
        raise AppError("document_context_not_found", "No relevant document context was found", status_code=404)
    context = "\n\n".join(f"[Source {i + 1}] {hit.content}" for i, hit in enumerate(sources))
    answer = await build_llm_service(request.app.state.settings).complete([
        {"role": "system", "content": "Answer only from the supplied sources. If they do not contain the answer, say so. Cite claims as [Source N]."},
        {"role": "user", "content": f"Question: {payload.query}\n\nSources:\n{context}"},
    ])
    return DocumentAnswer(answer=answer, sources=sources)


@router.get("/{document_id}", response_model=DocumentRead)
async def get_document(document_id: uuid.UUID, user: CurrentUser = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    document = await DocumentRepository(session).get_owned(document_id, user.id)
    if document is None:
        raise AppError("document_not_found", "Document not found", status_code=404)
    return document


@router.get("/{document_id}/content", response_model=DocumentContent)
async def get_document_content(document_id: uuid.UUID, user: CurrentUser = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    document = await DocumentRepository(session).get_owned(document_id, user.id)
    if document is None:
        raise AppError("document_not_found", "Document not found", status_code=404)
    if document.status != "ready" or not document.extracted_text:
        raise AppError("document_content_not_ready", "Document text is not ready", status_code=409)
    return DocumentContent(id=document.id, title=document.title, text=document.extracted_text)


@router.post("/{document_id}/summary", response_model=DocumentSummary)
async def summarize_document(document_id: uuid.UUID, request: Request, user: CurrentUser = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    payload = SearchRequest(query="main ideas, conclusions, and important details", document_id=document_id, limit=20)
    sources = await _search(payload, user, session, request)
    if not sources:
        raise AppError("document_context_not_found", "No document context was found", status_code=404)
    context = "\n\n".join(f"[Source {i + 1}] {hit.content}" for i, hit in enumerate(sources))
    summary = await build_llm_service(request.app.state.settings).complete([
        {"role": "system", "content": "Summarize the supplied document passages faithfully. Include the main ideas and conclusions. Cite supporting passages as [Source N]."},
        {"role": "user", "content": context},
    ])
    return DocumentSummary(summary=summary, sources=sources)
