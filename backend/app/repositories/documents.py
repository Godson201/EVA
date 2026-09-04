from __future__ import annotations

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Attachment, Document, DocumentChunk, ProcessingJob


class DocumentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_upload(self, user_id, object_key, filename, content_type, size, document_type):
        attachment = Attachment(user_id=user_id, object_key=object_key, original_filename=filename, content_type=content_type, size_bytes=size)
        self.session.add(attachment)
        await self.session.flush()
        document = Document(user_id=user_id, attachment_id=attachment.id, title=filename, document_type=document_type, status="pending", word_count=0)
        self.session.add(document)
        await self.session.flush()
        job = ProcessingJob(user_id=user_id, document_id=document.id, task_name="documents.process", status="pending")
        self.session.add(job)
        await self.session.flush()
        return attachment, document, job

    async def get_owned(self, document_id: uuid.UUID, user_id: uuid.UUID):
        return await self.session.scalar(select(Document).where(Document.id == document_id, Document.user_id == user_id))

    async def get_job_owned(self, job_id: uuid.UUID, user_id: uuid.UUID):
        return await self.session.scalar(select(ProcessingJob).where(ProcessingJob.id == job_id, ProcessingJob.user_id == user_id))

    async def list_owned(self, user_id, offset, limit):
        total = await self.session.scalar(select(func.count()).select_from(Document).where(Document.user_id == user_id)) or 0
        rows = await self.session.scalars(select(Document).where(Document.user_id == user_id).order_by(Document.created_at.desc()).offset(offset).limit(limit))
        return list(rows), total

    async def replace_chunks(self, document_id, chunks, embeddings):
        await self.session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
        self.session.add_all([
            DocumentChunk(document_id=document_id, chunk_index=chunk.index, content=chunk.content, page_number=chunk.page_number, embedding=embedding)
            for chunk, embedding in zip(chunks, embeddings, strict=True)
        ])

    async def search(self, user_id, embedding, limit=5, document_id=None):
        distance = DocumentChunk.embedding.cosine_distance(embedding)
        query = select(DocumentChunk, distance.label("distance")).join(Document).where(Document.user_id == user_id)
        if document_id:
            query = query.where(Document.id == document_id)
        rows = await self.session.execute(query.order_by(distance).limit(limit))
        return list(rows.all())
