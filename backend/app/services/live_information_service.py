from __future__ import annotations

import re
import asyncio
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from urllib.parse import urlsplit, urlunsplit

import httpx

from app.core.errors import AppError


LIVE_PATTERNS = (
    r"\b(latest|current|currently|today|tonight|yesterday|this week|breaking|news|headline|trend|trending|update|recent)\b",
    r"\b(politics|political|election|president|government|parliament|war|conflict)\b",
    r"\b(amakuru|uyu munsi|ibigezweho|amakuru mashya|politiki|amatora|leta|inteko)\b",
)
STOP_WORDS = {
    "what", "whats", "what's", "is", "are", "the", "a", "an", "about", "tell", "me", "show", "give",
    "please", "latest", "current", "currently", "today", "tonight", "this", "week", "news", "headlines",
    "update", "updates", "trending", "trend", "in", "on", "of", "for", "and", "from", "happening",
    "amakuru", "mashya", "uyu", "munsi", "mbwira", "nyereka", "kuri", "mu", "na", "ya",
}


@dataclass(frozen=True)
class LiveSource:
    id: int
    title: str
    url: str
    domain: str
    published_at: str | None
    language: str | None
    country: str | None

    def as_dict(self) -> dict:
        return asdict(self)


class GDELTLiveInformationService:
    _cache: dict[str, tuple[float, list[LiveSource]]] = {}
    _request_lock = asyncio.Lock()

    def __init__(self, settings, transport=None):
        self.base_url = settings.gdelt_base_url.strip()
        self.timeout = settings.gdelt_timeout_seconds
        self.max_results = settings.gdelt_max_results
        self.timespan = settings.gdelt_timespan
        self.cache_seconds = settings.gdelt_cache_seconds
        self.transport = transport

    @staticmethod
    def should_search(content: str) -> bool:
        normalized = content.casefold()
        return any(re.search(pattern, normalized, re.IGNORECASE) for pattern in LIVE_PATTERNS)

    @staticmethod
    def _query(content: str) -> str:
        words = re.findall(r"[\w'-]+", content, re.UNICODE)
        useful = [word for word in words if word.casefold() not in STOP_WORDS and len(word) > 1]
        return " ".join(useful[:12]) or "Rwanda"

    @staticmethod
    def _canonical_url(value: str) -> str:
        parts = urlsplit(value.strip())
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            return ""
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), "", ""))

    @staticmethod
    def _published(value: str | None) -> str | None:
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC).isoformat()
        except ValueError:
            return None

    async def search(self, content: str) -> list[LiveSource]:
        query = self._query(content)
        cache_key = f"{query.casefold()}|{self.timespan}|{self.max_results}"
        loop = asyncio.get_running_loop()
        cached = self._cache.get(cache_key)
        if cached and loop.time() - cached[0] < self.cache_seconds:
            return cached[1]
        params = {
            "query": query, "mode": "artlist", "format": "json", "sort": "datedesc",
            "maxrecords": self.max_results, "timespan": self.timespan,
        }
        try:
            async with self._request_lock:
                cached = self._cache.get(cache_key)
                if cached and loop.time() - cached[0] < self.cache_seconds:
                    return cached[1]
                async with httpx.AsyncClient(
                    timeout=self.timeout, follow_redirects=True, transport=self.transport,
                    headers={"User-Agent": "EVA-Live-Information/1.0 (GDELT news retrieval)"},
                ) as client:
                    response = await client.get(self.base_url, params=params)
                    if response.status_code == 429 and self.transport is None:
                        await asyncio.sleep(5)
                        response = await client.get(self.base_url, params=params)
                    response.raise_for_status()
                    payload = response.json()
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise AppError("live_search_unavailable", "Live information is temporarily unavailable", status_code=502) from exc

        articles = payload.get("articles", []) if isinstance(payload, dict) else []
        sources: list[LiveSource] = []
        seen_urls: set[str] = set()
        seen_titles: set[str] = set()
        for article in articles:
            if not isinstance(article, dict):
                continue
            url = self._canonical_url(str(article.get("url", "")))
            title = re.sub(r"\s+", " ", str(article.get("title", ""))).strip()
            title_key = re.sub(r"\W+", " ", title.casefold()).strip()
            if not url or not title or url in seen_urls or title_key in seen_titles:
                continue
            seen_urls.add(url); seen_titles.add(title_key)
            sources.append(LiveSource(
                id=len(sources) + 1, title=title, url=url,
                domain=str(article.get("domain") or urlsplit(url).netloc),
                published_at=self._published(article.get("seendate")),
                language=article.get("language"), country=article.get("sourcecountry"),
            ))
            if len(sources) >= self.max_results:
                break
        self._cache[cache_key] = (loop.time(), sources)
        return sources

    @staticmethod
    def context(sources: list[LiveSource]) -> str:
        today = datetime.now(UTC).date().isoformat()
        rows = [
            f"[{source.id}] {source.title} | publisher={source.domain} | published={source.published_at or 'unknown'} | "
            f"country={source.country or 'unknown'} | url={source.url}"
            for source in sources
        ]
        return (
            f"Today is {today}. The following are live GDELT headline records, not full article text. "
            "Answer the user's current-information question only with claims supported by these records. "
            "Cite supported statements as [1], [2], etc. Distinguish publication time from event time. "
            "Do not infer details that are absent from a headline. If evidence is insufficient or conflicting, say so.\n\n"
            + "\n".join(rows)
        )
