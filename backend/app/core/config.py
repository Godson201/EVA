"""Typed environment configuration for EVA V2."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="EVA_",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "EVA API"
    app_version: str = "2.0.0-dev"
    environment: Literal["development", "test", "staging", "production"] = "development"
    debug: bool = False
    docs_enabled: bool = True
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )
    secret_key: str = "eva-development-key-change-in-production"
    legacy_app_enabled: bool = False
    database_url: str = "postgresql+asyncpg://eva:eva@localhost:5432/eva"
    database_echo: bool = False
    embedding_dimensions: int = Field(default=768, ge=1, le=16000)
    legacy_mysql_host: str = "localhost"
    legacy_mysql_port: int = 3306
    legacy_mysql_user: str = "root"
    legacy_mysql_password: str = ""
    legacy_mysql_database: str = "audio_to_text"
    llm_provider: str = "anthropic"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"
    llm_timeout_seconds: float = Field(default=60, gt=0, le=300)
    translation_model: str = "facebook/nllb-200-distilled-600M"
    translation_max_input_chars: int = Field(default=20_000, ge=100, le=100_000)
    redis_url: str = "redis://localhost:6379/0"
    storage_backend: Literal["local", "s3"] = "local"
    storage_local_root: str = "storage"
    max_document_bytes: int = Field(default=25 * 1024 * 1024, ge=1024)
    embedding_model: str = "intfloat/multilingual-e5-base"
    s3_bucket: str = ""
    s3_endpoint_url: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_region: str = "auto"
    max_audio_bytes: int = Field(default=100 * 1024 * 1024, ge=1024)
    whisper_english_model: str = "openai/whisper-small"
    whisper_kinyarwanda_model: str = "pacomesimon/whisper-small-rw"
    memory_max_items_per_user: int = Field(default=100, ge=1, le=1000)
    memory_retrieval_limit: int = Field(default=5, ge=1, le=20)
    memory_max_content_chars: int = Field(default=1000, ge=50, le=10000)
    memory_max_retention_days: int = Field(default=365, ge=1, le=3650)
    access_token_minutes: int = Field(default=15, ge=1, le=1440)
    refresh_token_days: int = Field(default=30, ge=1, le=365)
    storage_encryption_key: str = ""
    voice_sample_min_seconds: float = Field(default=5.0, ge=1, le=30)
    voice_sample_max_seconds: float = Field(default=60.0, ge=10, le=300)
    voice_consent_version: str = "2026-09-v1"
    call_ticket_seconds: int = Field(default=60, ge=10, le=300)
    call_audio_queue_chunks: int = Field(default=32, ge=4, le=256)
    call_max_buffer_bytes: int = Field(default=5 * 1024 * 1024, ge=65536, le=50 * 1024 * 1024)

    @model_validator(mode="after")
    def validate_environment(self) -> "Settings":
        if not self.api_v1_prefix.startswith("/"):
            raise ValueError("api_v1_prefix must start with '/'")
        self.log_level = self.log_level.upper()
        if self.environment in {"staging", "production"}:
            if self.secret_key == "eva-development-key-change-in-production" or len(self.secret_key) < 32:
                raise ValueError("EVA_SECRET_KEY must contain at least 32 characters outside development")
            if self.debug:
                raise ValueError("debug must be disabled outside development and test")
            if not self.cors_origins:
                raise ValueError("at least one CORS origin is required")
            if not self.database_url.startswith("postgresql+"):
                raise ValueError("EVA_DATABASE_URL must use an async PostgreSQL driver")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
