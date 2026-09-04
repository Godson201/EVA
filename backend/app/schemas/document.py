from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class DocumentRead(BaseModel):
    id: uuid.UUID
    title: str
    document_type: str
    status: str
    word_count: int
    page_count: int | None
    error_message: str | None
    created_at: datetime
    model_config = {"from_attributes": True}


class DocumentUploadResult(BaseModel):
    document: DocumentRead
    job_id: uuid.UUID


class ProcessingJobRead(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID | None
    task_name: str
    status: str
    progress: int
    attempts: int
    error_message: str | None
    result: dict
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class DocumentList(BaseModel):
    items: list[DocumentRead]
    total: int


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    document_id: uuid.UUID | None = None
    limit: int = Field(default=5, ge=1, le=20)


class SearchHit(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    content: str
    page_number: int | None
    score: float


class QuestionRequest(SearchRequest):
    pass


class DocumentAnswer(BaseModel):
    answer: str
    sources: list[SearchHit]


class DocumentSummary(BaseModel):
    summary: str
    sources: list[SearchHit]
