from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pgvector.sqlalchemy import VECTOR
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import LegacyIdentityMixin, TimestampMixin, UUIDPrimaryKeyMixin

EMBEDDING_DIMENSIONS = 768


class Role(StrEnum):
    USER = "USER"
    ADMIN = "ADMIN"


class ProfileType(StrEnum):
    STUDENT = "student"
    TEACHER = "teacher"
    CALL_CENTER_AGENT = "call_center_agent"
    GENERAL_USER = "general_user"


class User(UUIDPrimaryKeyMixin, LegacyIdentityMixin, TimestampMixin, Base):
    __tablename__ = "users"
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default=Role.USER.value, index=True)
    profile_type: Mapped[str] = mapped_column(String(30), default=ProfileType.GENERAL_USER.value)
    provider: Mapped[str] = mapped_column(String(50), default="email")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RefreshToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "refresh_tokens"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(255), unique=True)
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replaced_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("refresh_tokens.id", ondelete="SET NULL"))


class PasswordResetToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "password_reset_tokens"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Conversation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "conversations"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str | None] = mapped_column(String(255))
    language: Mapped[str | None] = mapped_column(String(20))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Message(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "messages"
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20), index=True)
    content: Mapped[str] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(20))
    intent: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="completed")
    provider: Mapped[str | None] = mapped_column(String(50))
    model: Mapped[str | None] = mapped_column(String(100))
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)


class Attachment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "attachments"
    legacy_source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    legacy_id: Mapped[int | None] = mapped_column(nullable=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    message_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("messages.id", ondelete="SET NULL"), index=True)
    object_key: Mapped[str] = mapped_column(String(1024), unique=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(255))
    size_bytes: Mapped[int] = mapped_column(default=0)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64))
    __table_args__ = (UniqueConstraint("legacy_source", "legacy_id"),)


class Document(UUIDPrimaryKeyMixin, LegacyIdentityMixin, TimestampMixin, Base):
    __tablename__ = "documents"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    attachment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("attachments.id", ondelete="RESTRICT"), unique=True)
    title: Mapped[str] = mapped_column(String(255))
    document_type: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    extracted_text: Mapped[str | None] = mapped_column(Text)
    word_count: Mapped[int] = mapped_column(default=0)
    page_count: Mapped[int | None]
    error_message: Mapped[str | None] = mapped_column(Text)


class DocumentChunk(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "document_chunks"
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    chunk_index: Mapped[int]
    content: Mapped[str] = mapped_column(Text)
    page_number: Mapped[int | None]
    token_count: Mapped[int | None]
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    embedding: Mapped[list[float] | None] = mapped_column(VECTOR(EMBEDDING_DIMENSIONS))
    __table_args__ = (UniqueConstraint("document_id", "chunk_index"),)


class Transcription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "transcriptions"
    legacy_source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    legacy_id: Mapped[int | None] = mapped_column(nullable=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    attachment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("attachments.id", ondelete="SET NULL"))
    source: Mapped[str] = mapped_column(String(30), default="upload")
    language: Mapped[str | None] = mapped_column(String(20), index=True)
    raw_text: Mapped[str | None] = mapped_column(Text)
    corrected_text: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    key_points: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    timestamps: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(30), default="completed", index=True)
    model: Mapped[str | None] = mapped_column(String(100))
    __table_args__ = (UniqueConstraint("legacy_source", "legacy_id"),)


class Translation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "translations"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("conversations.id", ondelete="SET NULL"))
    source_text: Mapped[str] = mapped_column(Text)
    translated_text: Mapped[str] = mapped_column(Text)
    source_language: Mapped[str]
    target_language: Mapped[str]
    mode: Mapped[str] = mapped_column(String(30), default="natural")
    provider: Mapped[str | None] = mapped_column(String(50))


class VoiceProfile(UUIDPrimaryKeyMixin, LegacyIdentityMixin, TimestampMixin, Base):
    __tablename__ = "voice_profiles"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    attachment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("attachments.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(100))
    language: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(30), default="consent_pending", index=True)
    consent_version: Mapped[str | None] = mapped_column(String(30))
    consent_assertion: Mapped[str | None] = mapped_column(Text)
    purpose: Mapped[str | None] = mapped_column(String(255))
    consented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deletion_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    quality_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class Memory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "memories"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(50), index=True)
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(20), default="proposed", index=True)
    source_message_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("messages.id", ondelete="SET NULL"))
    provenance: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    embedding: Mapped[list[float] | None] = mapped_column(VECTOR(EMBEDDING_DIMENSIONS))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UserPreference(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_preferences"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    preferred_language: Mapped[str] = mapped_column(String(20), default="en")
    explanation_style: Mapped[str | None] = mapped_column(String(50))
    theme: Mapped[str] = mapped_column(String(30), default="indigo")
    font: Mapped[str] = mapped_column(String(30), default="inter")
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class VocabularyItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "vocabulary_items"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    term: Mapped[str] = mapped_column(String(255))
    language: Mapped[str] = mapped_column(String(20))
    definition: Mapped[str | None] = mapped_column(Text)
    translation: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (UniqueConstraint("user_id", "term", "language"),)


class StudyArtifact(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "study_artifacts"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("conversations.id", ondelete="SET NULL"), index=True)
    document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"), index=True)
    artifact_type: Mapped[str] = mapped_column(String(30), index=True)
    title: Mapped[str] = mapped_column(String(255))
    input_text: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(20), default="en")
    difficulty: Mapped[str] = mapped_column(String(20), default="intermediate")
    audience: Mapped[str] = mapped_column(String(100), default="general")
    length: Mapped[str] = mapped_column(String(20), default="medium")
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    source_refs: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    provider: Mapped[str | None] = mapped_column(String(50))
    model: Mapped[str | None] = mapped_column(String(100))


class CallSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "call_sessions"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="active", index=True)
    source_language: Mapped[str | None] = mapped_column(String(20))
    target_language: Mapped[str | None] = mapped_column(String(20))
    transcript: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    summary: Mapped[str | None] = mapped_column(Text)
    action_items: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    sentiment_cues: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ActivityLog(UUIDPrimaryKeyMixin, LegacyIdentityMixin, Base):
    __tablename__ = "activity_logs"
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    details: Mapped[str | None] = mapped_column(Text)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class ProcessingJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "processing_jobs"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    attachment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("attachments.id", ondelete="CASCADE"), index=True)
    transcription_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("transcriptions.id", ondelete="CASCADE"), index=True)
    task_name: Mapped[str] = mapped_column(String(100), index=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    progress: Mapped[int] = mapped_column(default=0)
    attempts: Mapped[int] = mapped_column(default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    result: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


Index("ix_document_chunks_embedding_hnsw", DocumentChunk.embedding, postgresql_using="hnsw", postgresql_ops={"embedding": "vector_cosine_ops"})
Index("ix_memories_embedding_hnsw", Memory.embedding, postgresql_using="hnsw", postgresql_ops={"embedding": "vector_cosine_ops"})
