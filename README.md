# EVA

EVA is an English–Kinyarwanda conversational, translation, speech, document, and learning assistant.

## Backend entry points

The existing application remains available during the EVA V2 migration:

```powershell
cd backend
python main.py
```

The lightweight modular V2 foundation can be started independently. It does not load Whisper or XTTS unless legacy compatibility is explicitly enabled:

```powershell
cd backend
uvicorn app.main:app --reload
```

Versioned health endpoints:

- `GET /api/v1/health/live`
- `GET /api/v1/health/ready`

Set `EVA_LEGACY_APP_ENABLED=True` to mount the original application under the V2 process. This compatibility mode loads the existing AI models and is intended only for migration testing until services are extracted in later phases.

Configuration keys and safe placeholders are documented in `.env.example`.

## PostgreSQL V2 schema

Phase 4 database setup and the non-destructive legacy migration workflow are documented in `docs/database-migration.md`.

## Core chat API

Phase 5 conversation endpoints, provider configuration, and streaming behavior are documented in `docs/core-chat.md`.

## Translation API

Phase 6 language detection, modes, NLLB fallback behavior, and API contracts are documented in `docs/translation.md`.

## Document intelligence

Phase 7 document processing, storage, worker, semantic search, and cited Q&A are documented in `docs/document-rag.md`.

## Speech processing

Phase 8 audio validation, queued Whisper transcription, unified TTS fallbacks, protected audio storage, and API contracts are documented in `docs/speech.md`.

## Personal memory

Phase 9 explicit-consent memory states, pgvector retrieval, retention controls, sensitive-data exclusions, and deletion behavior are documented in `docs/memory.md`.

## Next.js frontend migration

Phase 10 introduces the parallel `frontend-v2` Next.js application, central chat experience, session handling, route shells, and rollback strategy documented in `docs/frontend-v2.md`. The existing CRA frontend remains intact.

## Study mode

Phase 11 structured summaries, notes, explanations, quizzes, flashcards, vocabulary, document citations, and read-aloud integration are documented in `docs/study-mode.md`.

## Consent-based voice profiles

Phase 12 voice disclosures, audio quality gates, encrypted reference storage, revocation, export, permanent deletion, and the working Voice UI are documented in `docs/voice-profiles.md`.

## Call Assistant foundation

Phase 13 authenticated WebSocket sessions, bounded audio buffering, real-time event contracts, service reuse, persisted wrap-ups, and the internal simulator are documented in `docs/call-center.md`.
