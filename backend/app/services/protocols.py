"""Provider-independent contracts for later EVA phases.

Only contracts live here in Phase 3. Implementations remain in their assigned
migration phases.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LLMService(Protocol):
    async def complete(self, messages: list[dict[str, str]], **options: Any) -> str: ...

    def stream(self, messages: list[dict[str, str]], **options: Any) -> AsyncIterator[str]: ...


@runtime_checkable
class StorageService(Protocol):
    async def put(self, key: str, content: bytes, content_type: str) -> str: ...

    async def get(self, key: str) -> bytes: ...

    async def delete(self, key: str) -> None: ...

    async def put_private(self, key: str, content: bytes, content_type: str) -> str: ...

    async def get_private(self, key: str) -> bytes: ...


@runtime_checkable
class TranscriptionService(Protocol):
    async def transcribe(self, audio_path: Path, language: str | None = None) -> dict[str, Any]: ...


@runtime_checkable
class TranslationService(Protocol):
    async def translate(
        self,
        text: str,
        source_language: str | None,
        target_language: str,
        mode: str = "natural",
    ) -> dict[str, Any]: ...


@runtime_checkable
class TTSService(Protocol):
    async def synthesize(
        self,
        text: str,
        language: str,
        voice_id: str | None = None,
    ) -> dict[str, Any]: ...


@runtime_checkable
class EmbeddingService(Protocol):
    @property
    def dimensions(self) -> int: ...

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


@runtime_checkable
class JobService(Protocol):
    async def enqueue(self, task: str, payload: dict[str, Any]) -> str: ...

    async def status(self, job_id: str) -> dict[str, Any]: ...
