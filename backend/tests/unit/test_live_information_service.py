from __future__ import annotations

import asyncio

import httpx
import pytest

from app.core.config import Settings
from app.core.errors import AppError
from app.services.live_information_service import GDELTLiveInformationService


def service(handler):
    GDELTLiveInformationService._cache.clear()
    settings = Settings(
        environment="test", live_provider="gdelt", gdelt_max_results=3,
        gdelt_base_url="https://api.gdeltproject.org/api/v2/doc/doc", _env_file=None,
    )
    return GDELTLiveInformationService(settings, httpx.MockTransport(handler))


def test_detects_current_information_queries_in_both_languages():
    assert GDELTLiveInformationService.should_search("What is the latest education news in Rwanda?")
    assert GDELTLiveInformationService.should_search("Amakuru mashya ya politiki ni ayahe?")
    assert not GDELTLiveInformationService.should_search("Explain photosynthesis simply")


def test_gdelt_results_are_normalized_deduplicated_and_bounded():
    def handler(request):
        assert request.url.params["mode"] == "artlist"
        assert "Rwanda" in request.url.params["query"]
        return httpx.Response(200, json={"articles": [
            {"title":"Rwanda education update", "url":"https://example.com/story?tracking=1", "domain":"example.com", "seendate":"20260919T080000Z", "language":"English", "sourcecountry":"Rwanda"},
            {"title":"Rwanda education update", "url":"https://example.com/story-two", "domain":"example.com"},
            {"title":"University applications open", "url":"https://school.example/apply", "domain":"school.example", "seendate":"bad-date"},
        ]})

    results = asyncio.run(service(handler).search("latest Rwanda education news"))
    assert len(results) == 2
    assert results[0].id == 1
    assert results[0].url == "https://example.com/story"
    assert results[0].published_at == "2026-09-19T08:00:00+00:00"
    assert results[1].published_at is None


def test_gdelt_failure_has_safe_public_error():
    def handler(request):
        return httpx.Response(503, text="unavailable")

    with pytest.raises(AppError) as error:
        asyncio.run(service(handler).search("news in Rwanda today"))
    assert error.value.code == "live_search_unavailable"
