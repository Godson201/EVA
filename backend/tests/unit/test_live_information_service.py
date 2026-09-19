from __future__ import annotations

import asyncio

import httpx
import pytest

from app.core.config import Settings
from app.core.errors import AppError
from app.services.live_information_service import GDELTLiveInformationService, LiveSource


def service(handler):
    GDELTLiveInformationService._cache.clear()
    GDELTLiveInformationService._gdelt_unavailable_until = 0
    settings = Settings(
        environment="test", live_provider="gdelt", gdelt_max_results=3,
        gdelt_base_url="https://api.gdeltproject.org/api/v2/doc/doc", _env_file=None,
    )
    return GDELTLiveInformationService(settings, httpx.MockTransport(handler))


def test_detects_current_information_queries_in_both_languages():
    assert GDELTLiveInformationService.should_search("What is the latest education news in Rwanda?")
    assert GDELTLiveInformationService.should_search("What is the lastest education news in Rwanda?")
    assert GDELTLiveInformationService.should_search("Amakuru mashya ya politiki ni ayahe?")
    assert GDELTLiveInformationService.should_search("Uzi Bruce Melodie cyangwa Riderman?")
    assert GDELTLiveInformationService.should_search("The Ben uramuzi?")
    assert GDELTLiveInformationService.should_search("Naho Riderman?")
    assert GDELTLiveInformationService.should_search("indirimbo yitwa pom pom ni iyande?")
    assert GDELTLiveInformationService.should_search("Vestina ngo arimo gusaba gatanya?")
    assert GDELTLiveInformationService.should_search("Who are popular Rwandan musicians?")
    assert GDELTLiveInformationService.should_search("Who is the president of Kenya?")
    assert GDELTLiveInformationService.should_search("Ni nde uyobora Kenya?")
    assert not GDELTLiveInformationService.should_search("Explain photosynthesis simply")
    assert not GDELTLiveInformationService.should_search("Write a professional email")


def test_common_latest_typo_does_not_pollute_search_query():
    assert GDELTLiveInformationService._query("what is lastest news in rwanda education") == "rwanda education"


def test_the_ben_is_preserved_as_a_stage_name():
    assert GDELTLiveInformationService._query("The Ben uramuzi?") == '"The Ben" Rwanda musician'


@pytest.mark.parametrize(("question", "expected"), [
    ("uzi bruse melody?", '"Bruce Melodie" Rwanda singer'),
    ("naho Riderman", "Riderman Rwanda rapper"),
    ("Bull Dog uramuzi?", "Bulldogg Rwanda rapper"),
    ("uzi Bruce Melodie? yaririmbye izihe ndirimbo", '"Bruce Melodie" songs'),
    ("ese amakuru ya Vestine wo muri Vestina na Dorcas urayazi", '"Vestine and Dorcas" Rwanda latest news'),
])
def test_rwandan_artist_names_are_normalized(question, expected):
    assert GDELTLiveInformationService._query(question) == expected


def test_knowledge_search_uses_identified_client_and_returns_verified_excerpt():
    def handler(request):
        assert request.headers["user-agent"].startswith("EVA/1.0")
        return httpx.Response(200, json={"query": {"pages": {"1": {
            "title": "Bruce Melodie", "extract": "Bruce Melodie is a Rwandan singer.",
            "fullurl": "https://en.wikipedia.org/wiki/Bruce_Melodie",
        }}}})

    results = asyncio.run(service(handler)._knowledge_search('"Bruce Melodie" Rwanda singer'))
    assert results[0].excerpt == "Bruce Melodie is a Rwandan singer."


def test_general_factual_question_combines_knowledge_and_recent_coverage():
    rss = b"""<?xml version="1.0"?><rss><channel><item>
      <title>Example person appears at public event - Example News</title>
      <link>https://news.google.com/rss/articles/person</link>
      <pubDate>Fri, 18 Sep 2026 08:00:00 GMT</pubDate>
      <source url="https://example.org">Example News</source>
    </item></channel></rss>"""

    def handler(request):
        if "wikipedia.org" in request.url.host:
            return httpx.Response(200, json={"query": {"pages": {"1": {
                "title": "Example Person", "extract": "Example Person is a public official.",
                "fullurl": "https://en.wikipedia.org/wiki/Example_Person",
            }}}})
        return httpx.Response(200, content=rss)

    results = asyncio.run(service(handler).search("Who is Example Person?"))
    assert [source.domain for source in results] == ["en.wikipedia.org", "example.org"]
    assert results[0].excerpt == "Example Person is a public official."


def test_public_figure_answer_uses_only_verified_profile_and_source_titles():
    sources = [
        LiveSource(1, "Bruce Melodie", "https://example.org/bio", "example.org", None, "English", None,
                   "Bruce Melodie is a Rwandan singer."),
        LiveSource(2, "Bruce Melodie announces a concert", "https://news.example/story", "news.example",
                   "2026-09-18T08:00:00+00:00", "English", "Rwanda"),
    ]
    answer = GDELTLiveInformationService.public_figure_answer("uzi bruse melody?", sources, "rw")
    assert answer == "Yego, ndamuzi. Bruce Melodie ni umuhanzi w'Umunyarwanda. [1]"


def test_music_catalog_returns_exact_song_credit():
    def handler(request):
        assert request.url.params["entity"] == "song"
        return httpx.Response(200, json={"results": [{
            "trackName": "Pom Pom",
            "artistName": "Bruce Melodie, Diamond Platnumz & Brown Joel",
            "trackViewUrl": "https://music.apple.com/us/album/pom-pom/1?i=2",
            "releaseDate": "2026-01-01T12:00:00Z",
        }]})

    results = asyncio.run(service(handler)._music_catalog_search('"Pom Pom" "Bruce Melodie"'))
    assert results[0].title == "Pom Pom — Bruce Melodie, Diamond Platnumz & Brown Joel"
    assert results[0].url == "https://music.apple.com/us/album/pom-pom/1"


def test_musicbrainz_resolves_an_unfamiliar_rwandan_artist():
    def handler(request):
        return httpx.Response(200, json={"artists": [{
            "id": "artist-id", "name": "Bulldogg", "score": 99,
            "disambiguation": "Rwandan rapper",
        }]})

    results = asyncio.run(service(handler)._artist_search("Bulldogg Rwanda rapper"))
    assert results[0].title == "Bulldogg"
    assert results[0].country == "Rwanda"


def test_song_owner_answer_is_direct_and_grounded():
    sources = [LiveSource(
        1, "Bruce Melodie - Pom Pom ft. Diamond Platnumz, Brown Joel", "https://music.example/pom-pom",
        "music.example", "2026-01-01T00:00:00+00:00", "English", None,
    )]
    answer = GDELTLiveInformationService.public_figure_answer(
        "indirimbo yitwa pom pom urayizi se ni iyande?", sources, "rw",
    )
    assert "Bruce Melodie" in answer
    assert "Diamond Platnumz" in answer
    assert answer.endswith("[1]")


def test_divorce_claim_is_treated_as_ongoing_legal_news():
    sources = [LiveSource(
        1, "Ishimwe Vestine confirms divorce proceedings", "https://news.example/vestine",
        "news.example", "2026-09-14T08:00:00+00:00", "English", "Rwanda",
    )]
    answer = GDELTLiveInformationService.public_figure_answer(
        "vestina ngo arimo gusaba gatanya we n'umugabo we?", sources, "rw",
    )
    assert "inzira y’amategeko" in answer
    assert "rugikomeje" in answer
    assert answer.endswith("[1]")


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


def test_empty_week_expands_search_to_one_month():
    calls = []

    def handler(request):
        calls.append(request.url.params["timespan"])
        if len(calls) == 1:
            return httpx.Response(200, json={"articles": []})
        return httpx.Response(200, json={"articles": [{
            "title": "Rwanda education programme announced",
            "url": "https://education.example/rwanda-programme",
        }]})

    results = asyncio.run(service(handler).search("latest Rwanda education news"))
    assert calls == ["1week", "1month"]
    assert len(results) == 1


def test_rate_limited_gdelt_uses_keyless_news_rss_fallback():
    rss = b"""<?xml version="1.0"?><rss><channel><item>
      <title>Rwanda launches new education programme - Example News</title>
      <link>https://news.google.com/rss/articles/example?oc=5</link>
      <pubDate>Fri, 18 Sep 2026 08:00:00 GMT</pubDate>
      <source url="https://example.org">Example News</source>
    </item></channel></rss>"""

    def handler(request):
        if "gdeltproject.org" in request.url.host:
            return httpx.Response(429, text="rate limited")
        assert request.url.params["q"] == "rwanda education"
        return httpx.Response(200, content=rss)

    results = asyncio.run(service(handler).search("lastest news in rwanda education"))
    assert len(results) == 1
    assert results[0].domain == "example.org"
    assert results[0].published_at == "2026-09-18T08:00:00+00:00"
