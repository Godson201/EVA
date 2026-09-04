from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.core.config import Settings
from app.core.errors import AppError


class AnthropicLLMService:
    endpoint = "https://api.anthropic.com/v1/messages"

    def __init__(self, settings: Settings):
        self.api_key = settings.anthropic_api_key
        self.model = settings.anthropic_model
        self.timeout = settings.llm_timeout_seconds

    def _payload(self, messages: list[dict[str, str]], stream: bool = False) -> dict[str, Any]:
        system = "\n\n".join(item["content"] for item in messages if item["role"] == "system")
        conversation = [item for item in messages if item["role"] in {"user", "assistant"}]
        return {"model": self.model, "max_tokens": 2048, "system": system, "messages": conversation, "stream": stream}

    @property
    def _headers(self) -> dict[str, str]:
        return {"x-api-key": self.api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}

    async def complete(self, messages: list[dict[str, str]], **options: Any) -> str:
        if not self.api_key:
            raise AppError("llm_not_configured", "The conversational AI provider is not configured", status_code=503)
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.endpoint, headers=self._headers, json=self._payload(messages))
                response.raise_for_status()
            return "".join(block.get("text", "") for block in response.json().get("content", []))
        except httpx.HTTPError as exc:
            raise AppError("llm_provider_error", "The conversational AI provider is unavailable", status_code=502) from exc

    async def stream(self, messages: list[dict[str, str]], **options: Any) -> AsyncIterator[str]:
        if not self.api_key:
            raise AppError("llm_not_configured", "The conversational AI provider is not configured", status_code=503)
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("POST", self.endpoint, headers=self._headers, json=self._payload(messages, True)) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        event = json.loads(line[6:])
                        if event.get("type") == "content_block_delta" and event.get("delta", {}).get("type") == "text_delta":
                            yield event["delta"]["text"]
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            raise AppError("llm_provider_error", "The conversational AI provider is unavailable", status_code=502) from exc


class GroqLLMService:
    endpoint = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, settings: Settings):
        self.api_key = settings.groq_api_key
        self.model = settings.groq_model
        self.timeout = settings.llm_timeout_seconds

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def _payload(self, messages: list[dict[str, str]], stream: bool = False) -> dict[str, Any]:
        return {"model": self.model, "messages": messages, "max_completion_tokens": 2048, "stream": stream}

    def _ensure_configured(self) -> None:
        if not self.api_key:
            raise AppError("llm_not_configured", "The Groq API key is not configured", status_code=503)

    async def complete(self, messages: list[dict[str, str]], **options: Any) -> str:
        self._ensure_configured()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.endpoint, headers=self._headers, json=self._payload(messages))
                response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError, TypeError) as exc:
            raise AppError("llm_provider_error", "Groq is currently unavailable or has reached its free-tier limit", status_code=502) from exc

    async def stream(self, messages: list[dict[str, str]], **options: Any) -> AsyncIterator[str]:
        self._ensure_configured()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("POST", self.endpoint, headers=self._headers, json=self._payload(messages, True)) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.startswith("data: ") or line == "data: [DONE]":
                            continue
                        event = json.loads(line[6:])
                        content = event.get("choices", [{}])[0].get("delta", {}).get("content")
                        if content:
                            yield content
        except (httpx.HTTPError, json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise AppError("llm_provider_error", "Groq is currently unavailable or has reached its free-tier limit", status_code=502) from exc


class DeterministicLLMService:
    """Predictable provider for tests; never selected by production settings."""
    model = "deterministic-test"

    async def complete(self, messages: list[dict[str, str]], **options: Any) -> str:
        prompt = next(item["content"] for item in reversed(messages) if item["role"] == "user")
        return f"EVA test response: {prompt}"

    async def stream(self, messages: list[dict[str, str]], **options: Any) -> AsyncIterator[str]:
        for word in (await self.complete(messages)).split(" "):
            yield word + " "


def build_llm_service(settings: Settings):
    if settings.llm_provider == "anthropic":
        return AnthropicLLMService(settings)
    if settings.llm_provider == "groq":
        return GroqLLMService(settings)
    raise ValueError(f"Unsupported EVA_LLM_PROVIDER: {settings.llm_provider}")
