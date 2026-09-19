# Live information with GDELT

EVA can ground current-information chat answers in the public GDELT DOC 2.0 API without an API key.

## Configuration

Add these values to `backend/.env`:

```env
EVA_LIVE_PROVIDER=gdelt
EVA_GDELT_BASE_URL=https://api.gdeltproject.org/api/v2/doc/doc
EVA_GDELT_TIMEOUT_SECONDS=20
EVA_GDELT_MAX_RESULTS=8
EVA_GDELT_TIMESPAN=1week
EVA_GDELT_CACHE_SECONDS=300
```

Restart the API after editing `.env`. The frontend globe button forces live retrieval for a message. EVA also enables it automatically for clearly time-sensitive English and Kinyarwanda questions.

## Answer contract

- GDELT results are sorted newest-first, normalized, deduplicated, and cached briefly to respect anonymous rate limits.
- Only valid HTTP(S) source URLs are retained.
- The language model receives headline metadata, publisher, publication time, country, and URL. It is instructed not to infer facts absent from those records.
- Each saved assistant message retains its live-source metadata. The chat UI displays sources in an expandable, owner-visible list.
- Publication time is not represented as the time an event occurred.

GDELT can be incomplete or noisy. EVA therefore presents live results as sourced reporting rather than established truth, and users should verify important claims using the linked publisher pages.
