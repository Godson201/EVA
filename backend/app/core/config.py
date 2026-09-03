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
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
