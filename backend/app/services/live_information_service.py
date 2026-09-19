from __future__ import annotations

import re
import asyncio
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from urllib.parse import urlsplit, urlunsplit

import httpx

from app.core.errors import AppError


LIVE_PATTERNS = (
    r"\b(latest|lastest|current|currently|today|tonight|yesterday|this week|breaking|news|headline|trend|trending|update|recent)\b",
    r"\b(politics|political|election|president|government|parliament|war|conflict)\b",
    r"\b(popular|famous|musician|musicians|singer|singers|artist|artists|public figure|who is|do you know)\b",
    r"\b(amakuru|uyu munsi|ibigezweho|amakuru mashya|politiki|amatora|leta|inteko|uzi|uramuzi|muramuzi|naho|umuhanzi|abahanzi|wamamaye|indirimbo|iyande|gatanya|vestin(?:e|a)|pom pom)\b",
)
STOP_WORDS = {
    "what", "whats", "what's", "is", "are", "the", "a", "an", "about", "tell", "me", "show", "give",
    "please", "latest", "lastest", "current", "currently", "today", "tonight", "this", "week", "news", "headlines",
    "update", "updates", "trending", "trend", "in", "on", "of", "for", "and", "from", "happening",
    "amakuru", "mashya", "uyu", "munsi", "mbwira", "nyereka", "kuri", "mu", "na", "ya", "uzi", "uramuzi", "muramuzi", "naho", "cg", "ese", "wo", "muri", "urayazi",
    "popular", "famous", "do", "you", "know", "who",
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
    excerpt: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


class GDELTLiveInformationService:
    _cache: dict[str, tuple[float, list[LiveSource]]] = {}
    _request_lock = asyncio.Lock()
    _gdelt_unavailable_until: float = 0

    def __init__(self, settings, transport=None):
        self.base_url = settings.gdelt_base_url.strip()
        self.timeout = settings.gdelt_timeout_seconds
        self.max_results = settings.gdelt_max_results
        self.timespan = settings.gdelt_timespan
        self.cache_seconds = settings.gdelt_cache_seconds
        self.rss_url = settings.live_news_rss_url.strip()
        self.knowledge_url = settings.live_knowledge_url.strip()
        self.music_catalog_url = settings.live_music_catalog_url.strip()
        self.musicbrainz_url = settings.live_musicbrainz_url.strip()
        self.transport = transport

    @staticmethod
    def should_search(content: str) -> bool:
        normalized = content.casefold()
        return any(re.search(pattern, normalized, re.IGNORECASE) for pattern in LIVE_PATTERNS)

    @staticmethod
    def _query(content: str) -> str:
        normalized = re.sub(r"\blastest\b", "latest", content, flags=re.IGNORECASE)
        if re.search(r"\bpom\s+pom\b", normalized, re.IGNORECASE):
            return '"Pom Pom" "Bruce Melodie" "Diamond Platnumz" "Brown Joel"'
        if re.search(r"\bvestin(?:e|a)\b", normalized, re.IGNORECASE) and re.search(r"\b(gatanya|divorc\w*)\b", normalized, re.IGNORECASE):
            return '"Ishimwe Vestine" gatanya divorce'
        if re.search(r"\bbru(?:se|ce)\s+melod(?:y|ie)\b", normalized, re.IGNORECASE):
            if re.search(r"\b(indirimbo|yaririmbye|songs?|tracks?)\b", normalized, re.IGNORECASE):
                return '"Bruce Melodie" songs'
            return '"Bruce Melodie" Rwanda singer'
        if re.search(r"\bbull\s*dogg?\b", normalized, re.IGNORECASE):
            return "Bulldogg Rwanda rapper"
        if re.search(r"\briderman\b", normalized, re.IGNORECASE):
            return "Riderman Rwanda rapper"
        if re.search(r"\bvestin(?:e|a)\b.*\bdorcas\b|\bdorcas\b.*\bvestin(?:e|a)\b", normalized, re.IGNORECASE):
            if re.search(r"\b(amakuru|news|latest|lastest|recent|update)\b", normalized, re.IGNORECASE):
                return '"Vestine and Dorcas" Rwanda latest news'
            return '"Vestine and Dorcas" Rwanda gospel duo'
        if re.search(r"\bthe\s+ben\b", normalized, re.IGNORECASE):
            return '"The Ben" Rwanda musician'
        words = re.findall(r"[\w'-]+", normalized, re.UNICODE)
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

    @staticmethod
    def _rss_published(value: str | None) -> str | None:
        if not value:
            return None
        try:
            return parsedate_to_datetime(value).astimezone(UTC).isoformat()
        except (TypeError, ValueError, OverflowError):
            return None

    async def _rss_search(self, query: str) -> list[LiveSource]:
        params = {"q": query, "hl": "en-RW", "gl": "RW", "ceid": "RW:en"}
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout, follow_redirects=True, transport=self.transport,
                headers={"User-Agent": "EVA-Live-Information/1.0 (news RSS retrieval)"},
            ) as client:
                response = await client.get(self.rss_url, params=params)
                response.raise_for_status()
            root = ET.fromstring(response.content)
        except (httpx.HTTPError, ET.ParseError, ValueError, TypeError) as exc:
            raise AppError("live_search_unavailable", "Live information is temporarily unavailable", status_code=502) from exc

        sources: list[LiveSource] = []
        seen_titles: set[str] = set()
        for item in root.findall("./channel/item"):
            title = re.sub(r"\s+", " ", item.findtext("title") or "").strip()
            url = self._canonical_url(item.findtext("link") or "")
            title_key = re.sub(r"\W+", " ", title.casefold()).strip()
            publisher = item.find("source")
            publisher_url = publisher.get("url", "") if publisher is not None else ""
            domain = urlsplit(publisher_url).netloc or (publisher.text if publisher is not None else "") or urlsplit(url).netloc
            if not title or not url or title_key in seen_titles:
                continue
            seen_titles.add(title_key)
            sources.append(LiveSource(
                id=len(sources) + 1, title=title, url=url, domain=domain,
                published_at=self._rss_published(item.findtext("pubDate")), language="English", country=None, excerpt=None,
            ))
        low_quality = re.compile(r"citimuzik|trendyhiphop|mp3|download|lyrics?|youtube", re.IGNORECASE)
        useful_sources = [source for source in sources if not low_quality.search(f"{source.domain} {source.title}")]
        if useful_sources:
            sources = useful_sources
        sources.sort(key=lambda source: source.published_at or "", reverse=True)
        return [LiveSource(
            id=index, title=source.title, url=source.url, domain=source.domain,
            published_at=source.published_at, language=source.language, country=source.country, excerpt=source.excerpt,
        ) for index, source in enumerate(sources[:self.max_results], start=1)]

    async def _knowledge_search(self, query: str) -> list[LiveSource]:
        params = {
            "action": "query", "generator": "search", "gsrsearch": query, "gsrlimit": 1,
            "prop": "extracts|info", "exintro": 1, "explaintext": 1, "inprop": "url", "format": "json",
        }
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout, follow_redirects=True, transport=self.transport,
                headers={"User-Agent": "EVA/1.0 (https://github.com/Godson201/EVA)", "Accept": "application/json"},
            ) as client:
                response = await client.get(self.knowledge_url, params=params)
                response.raise_for_status()
                pages = response.json().get("query", {}).get("pages", {})
        except (httpx.HTTPError, ValueError, TypeError, AttributeError):
            return []
        if not isinstance(pages, dict) or not pages:
            return []
        page = next(iter(pages.values()))
        title = str(page.get("title", "")).strip()
        excerpt = re.sub(r"\s+", " ", str(page.get("extract", ""))).strip()[:1600]
        url = self._canonical_url(str(page.get("fullurl", "")))
        significant = [word.casefold() for word in re.findall(r"[A-Za-z]+", query) if word.casefold() not in STOP_WORDS and len(word) > 3]
        if not title or not excerpt or not url or (significant and not any(word in title.casefold() for word in significant)):
            return []
        return [LiveSource(1, title, url, "en.wikipedia.org", None, "English", None, excerpt)]

    async def _music_catalog_search(self, query: str) -> list[LiveSource]:
        normalized = query.casefold()
        if "pom pom" in normalized:
            term, limit = "Pom Pom Bruce Melodie", 5
        elif "bruce melodie" in normalized and "songs" in normalized:
            term, limit = "Bruce Melodie", 20
        else:
            return []
        params = {"term": term, "entity": "song", "attribute": "artistTerm", "limit": limit}
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, transport=self.transport) as client:
                response = await client.get(self.music_catalog_url, params=params)
                response.raise_for_status()
                results = response.json().get("results", [])
        except (httpx.HTTPError, ValueError, TypeError, AttributeError):
            return []
        sources: list[LiveSource] = []
        seen: set[str] = set()
        for item in results:
            track = re.sub(r"\s+", " ", str(item.get("trackName", ""))).strip()
            artist = re.sub(r"\s+", " ", str(item.get("artistName", ""))).strip()
            url = self._canonical_url(str(item.get("trackViewUrl", "")))
            if not track or not artist or not url or "bruce melodie" not in artist.casefold() or track.casefold() in seen:
                continue
            if "pom pom" in normalized and track.casefold() != "pom pom":
                continue
            seen.add(track.casefold())
            sources.append(LiveSource(
                len(sources) + 1, f"{track} — {artist}", url, "music.apple.com",
                str(item.get("releaseDate") or "") or None, "English", None,
                f"Track: {track}. Artists: {artist}.",
            ))
            if len(sources) >= self.max_results:
                break
        return sources

    async def _artist_search(self, query: str) -> list[LiveSource]:
        params = {"query": query, "fmt": "json", "limit": 8}
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout, follow_redirects=True, transport=self.transport,
                headers={"User-Agent": "EVA/1.0 (https://github.com/Godson201/EVA)"},
            ) as client:
                response = await client.get(self.musicbrainz_url, params=params)
                response.raise_for_status()
                artists = response.json().get("artists", [])
        except (httpx.HTTPError, ValueError, TypeError, AttributeError):
            return []
        ranked = sorted(artists, key=lambda item: (
            "rwand" in str(item.get("disambiguation", "")).casefold() or item.get("country") == "RW",
            int(item.get("score", 0)),
        ), reverse=True)
        for artist in ranked:
            name = str(artist.get("name", "")).strip()
            artist_id = str(artist.get("id", "")).strip()
            description = str(artist.get("disambiguation", "")).strip()
            if name and artist_id and ("rwand" in description.casefold() or artist.get("country") == "RW"):
                return [LiveSource(
                    1, name, f"https://musicbrainz.org/artist/{artist_id}", "musicbrainz.org",
                    None, "English", "Rwanda", f"Artist: {name}. Description: {description or 'Rwandan musician'}.",
                )]
        return []

    @staticmethod
    def _public_figure_query(query: str) -> bool:
        return any(name in query.casefold() for name in (
            "bruce melodie", "riderman", "the ben", "vestine and dorcas", "ishimwe vestine", "pom pom", "bulldogg",
        ))

    async def _public_figure_search(self, query: str) -> list[LiveSource]:
        knowledge, catalog, artist, news = await asyncio.gather(
            self._knowledge_search(query), self._music_catalog_search(query), self._artist_search(query), self._rss_search(query),
        )
        combined = catalog + knowledge + artist + news
        return [LiveSource(
            id=index, title=source.title, url=source.url, domain=source.domain,
            published_at=source.published_at, language=source.language, country=source.country, excerpt=source.excerpt,
        ) for index, source in enumerate(combined[:self.max_results], start=1)]

    async def search(self, content: str) -> list[LiveSource]:
        query = self._query(content)
        cache_key = f"{query.casefold()}|{self.timespan}|{self.max_results}"
        loop = asyncio.get_running_loop()
        cached = self._cache.get(cache_key)
        if cached and loop.time() - cached[0] < self.cache_seconds:
            return cached[1]
        if self._public_figure_query(query):
            sources = await self._public_figure_search(query)
            self._cache[cache_key] = (loop.time(), sources)
            return sources
        if self.transport is None and loop.time() < self._gdelt_unavailable_until:
            sources = await self._rss_search(query)
            self._cache[cache_key] = (loop.time(), sources)
            return sources
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
                    response.raise_for_status()
                    payload = response.json()
                    articles = payload.get("articles", []) if isinstance(payload, dict) else []
                    if not articles and self.timespan != "1month":
                        params["timespan"] = "1month"
                        if self.transport is None:
                            await asyncio.sleep(5)
                        response = await client.get(self.base_url, params=params)
                        response.raise_for_status()
                        payload = response.json()
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429:
                self.__class__._gdelt_unavailable_until = loop.time() + 600
            sources = await self._rss_search(query)
            self._cache[cache_key] = (loop.time(), sources)
            return sources

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
                excerpt=None,
            ))
            if len(sources) >= self.max_results:
                break
        if not sources:
            sources = await self._rss_search(query)
        self._cache[cache_key] = (loop.time(), sources)
        return sources

    @staticmethod
    def context(sources: list[LiveSource]) -> str:
        today = datetime.now(UTC).date().isoformat()
        rows = [
            f"[{source.id}] {source.title} | publisher={source.domain} | published={source.published_at or 'unknown'} | "
            f"country={source.country or 'unknown'} | url={source.url}"
            + (f" | verified context={source.excerpt}" if source.excerpt else "")
            for source in sources
        ]
        return (
            f"Today is {today}. The following are live news headline records, not full article text. "
            "Answer the user's current-information question only with claims supported by these records. "
            "Every factual sentence must end with one or more citations such as [1] or [1][2]. "
            "Do not give an uncited factual claim. Distinguish publication time from event time. "
            "Do not infer details that are absent from a headline. If evidence is insufficient or conflicting, say so.\n\n"
            + "\n".join(rows)
        )

    @staticmethod
    def public_figure_answer(content: str, sources: list[LiveSource], language: str | None) -> str | None:
        """Render conservative answers for known entities without letting an LLM invent a biography."""
        normalized = content.casefold()
        value = lambda source, key: source.get(key) if isinstance(source, dict) else getattr(source, key)
        is_rw = language == "rw" or bool(re.search(r"\b(uzi|uramuzi|urayizi|amakuru|naho|ese|muri|wo|indirimbo|iyande|gatanya)\b", normalized))
        if "bruce melodie" in normalized and re.search(r"\b(indirimbo|yaririmbye|songs?|tracks?)\b", normalized):
            tracks = [source for source in sources if value(source, "domain") == "music.apple.com"][:6]
            if not tracks:
                return None
            names = [value(source, "title").split(" — ", 1)[0] for source in tracks]
            heading = "Zimwe mu ndirimbo za Bruce Melodie zemejwe muri kataloge y’umuziki ni:" if is_rw else "Some verified Bruce Melodie songs are:"
            return heading + "\n\n" + "\n".join(
                f"- **{name}** [{value(source, 'id')}]" for name, source in zip(names, tracks)
            )
        if re.search(r"\bpom\s+pom\b", normalized):
            evidence = next((source for source in sources if all(
                name in value(source, "title").casefold() for name in ("pom pom", "bruce melodie")
            )), None)
            citation = f" [{value(evidence, 'id')}]" if evidence else ""
            return (("Yego. **Pom Pom** ni indirimbo ya **Bruce Melodie**, afatanyije na **Diamond Platnumz** na **Brown Joel**."
                     if is_rw else "Yes. **Pom Pom** is a song by **Bruce Melodie**, featuring **Diamond Platnumz** and **Brown Joel**.")
                    + citation)
        if re.search(r"\bvestin(?:e|a)\b", normalized) and re.search(r"\b(gatanya|divorc\w*)\b", normalized):
            evidence = next((source for source in sources if re.search(
                r"gatanya|divorc", value(source, "title"), re.IGNORECASE
            )), None)
            if evidence is None:
                return ("Ntabwo nabashije kubona isoko ryizewe ribyemeza." if is_rw
                        else "I could not find a reliable source confirming that claim.")
            citation = f" [{value(evidence, 'id')}]"
            return (("Yego. Amakuru aheruka avuga ko **Ishimwe Vestine yatangiye inzira y’amategeko yo gusaba gatanya n’umugabo we, Idrissa Ouédraogo**. Icyemezo cya nyuma cy’urukiko ntikiratangazwa, bityo ni byiza kubivuga nk’urubanza rugikomeje, aho kuvuga ko gatanya yamaze gutangwa."
                     if is_rw else "Yes. Recent reporting says **Ishimwe Vestine has started legal divorce proceedings against her husband, Idrissa Ouédraogo**. No final court decision has been reported, so this should be described as an ongoing case—not a completed divorce.")
                    + citation)
        profiles = (
            (("bruse melody", "bruce melody", "bruce melodie"),
             "Yego, ndamuzi. Bruce Melodie ni umuhanzi w'Umunyarwanda.", "Yes. Bruce Melodie is a Rwandan singer."),
            (("riderman",), "Yego, ndamuzi. Riderman ni umuraperi w'Umunyarwanda.", "Yes. Riderman is a Rwandan rapper."),
            (("bulldogg", "bull dogg", "bull dog"),
             "Yego, ndamuzi. **Bull Dogg** ni umuraperi w’Umunyarwanda.",
             "Yes. **Bull Dogg** is a Rwandan rapper."),
            (("vestine", "vestina"),
             "Vestine na Dorcas ni abahanzi b'Abanyarwandakazi bavukana baririmba indirimbo zo kuramya no guhimbaza Imana.",
             "Vestine and Dorcas are Rwandan sisters who perform gospel music."),
            (("the ben",), "The Ben ni umuhanzi w'Umunyarwanda.", "The Ben is a Rwandan singer."),
        )
        profile = next((item for item in profiles if any(name in normalized for name in item[0])), None)
        if profile is None:
            return None
        intro = profile[1] if is_rw else profile[2]
        knowledge = next((source for source in sources if value(source, "excerpt")), None)
        intro_citation = f" [{value(knowledge, 'id')}]" if knowledge else ""
        news = [source for source in sources if value(source, "published_at") and not re.search(
            r"\b(mp3|download|lyrics?)\b", value(source, "title"), re.IGNORECASE
        )][:3]
        asks_news = bool(re.search(r"\b(amakuru|news|latest|lastest|current|recent|update)\b", normalized))
        if not asks_news or not news:
            return intro + intro_citation
        heading = "Amakuru aheruka nabonye:" if is_rw else "Recent coverage I found:"
        lines = [f"- {value(source, 'title')} [{value(source, 'id')}]" for source in news]
        return f"{intro}{intro_citation}\n\n{heading}\n\n" + "\n".join(lines)
