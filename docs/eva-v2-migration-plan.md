# EVA V2 Incremental Migration Plan

## Purpose

This plan migrates the existing EVA audio-focused prototype into a modular conversational assistant without discarding working transcription, document, translation, TTS, authentication, or dashboard functionality.

The migration uses a strangler pattern: new `/api/v1` capabilities are introduced beside legacy endpoints, and old code is retired only after its replacement passes automated and manual compatibility checks.

## Non-negotiable migration rules

1. Keep the current React frontend and legacy FastAPI application runnable during the migration.
2. Do not delete a legacy feature until its replacement is verified.
3. Put new backend code under `backend/app/`; do not expand `backend/main.py`.
4. Add new APIs under `/api/v1` unless an existing public contract must be preserved.
5. Move business logic behind service interfaces before changing its implementation.
6. Treat PostgreSQL as a parallel data store until migration validation succeeds.
7. Require explicit user consent for memory and voice-profile retention.
8. Keep AI providers replaceable through interfaces and configuration.
9. Execute long-running work outside the web request process once the job foundation exists.
10. End every phase with tests, a migration note, and a rollback checkpoint.

## Target architecture

EVA V2 remains a modular monolith with three runtime processes:

- `web`: FastAPI HTTP and WebSocket application
- `worker`: Celery tasks for long-running AI and document operations
- `frontend`: Next.js application, introduced beside the current React SPA

Shared infrastructure:

- PostgreSQL with pgvector
- Redis for Celery and transient coordination
- S3-compatible storage interface with a local development implementation
- Configured AI providers behind service protocols

## API compatibility strategy

The existing routes remain available during backend migration. New clients use `/api/v1`.

| Legacy area | V2 destination | Compatibility approach |
|---|---|---|
| `/api/auth/*` | `/api/v1/auth/*` | Keep legacy login response while adding access/refresh token endpoints |
| `/upload`, `/records`, `/record/*` | `/api/v1/transcriptions/*` | Legacy handlers delegate to the new transcription service |
| `/api/speech/*` | `/api/v1/transcriptions/*` | Normalize uploaded and browser-recorded speech into one model |
| `/api/translate` | `/api/v1/translations` | Preserve the old request shape through an adapter |
| `/api/text/analyze` | `/api/v1/assistant/analyze` | Move summarization and key points behind AI services |
| `/tts/*` | `/api/v1/voices`, `/api/v1/speech/synthesize`, `/api/v1/documents` | Preserve URLs until the frontend migrates |
| `/api/user/*` | `/api/v1/users/me/*` | Map legacy fields to the new profile/preferences model |
| `/api/admin/*` | `/api/v1/admin/*` | Introduce the simplified `USER`/`ADMIN` authorization model with temporary role mapping |

Deprecation requires all of the following:

- Replacement endpoint tests pass.
- The current frontend no longer calls the legacy endpoint.
- Data ownership behavior is equivalent or stricter.
- A release note identifies the replacement.
- At least one rollback-compatible release retains the adapter.

## Role compatibility

V2 permission roles are `USER` and `ADMIN`. Existing roles are mapped during transition:

| Existing role | V2 permission role | Suggested profile type |
|---|---|---|
| `user` | `USER` | `general_user` |
| `secretary` | `USER` | `general_user` |
| `manager` | `ADMIN` initially | `general_user` |
| `director` | `ADMIN` | `general_user` |
| `admin` | `ADMIN` | `general_user` |

The manager mapping must be reviewed against real permissions before legacy roles are removed. Profile types (`student`, `teacher`, `call_center_agent`, `general_user`) describe experience preferences and never grant permissions.

## Phase sequence and gates

### Phase 3 — Backend foundation

Goal: establish a modular FastAPI application without changing core behavior or database technology.

Add:

```text
backend/app/
  main.py
  api/router.py
  api/v1/router.py
  api/v1/endpoints/health.py
  core/config.py
  core/logging.py
  core/errors.py
  schemas/common.py
  services/protocols.py
backend/tests/unit/
backend/tests/integration/
```

Work:

- Add typed environment configuration and production validation.
- Add structured logging and request correlation IDs.
- Add standard error responses and exception handlers.
- Add `/api/v1/health/live` and `/api/v1/health/ready`.
- Define service protocols for LLM, storage, transcription, translation, TTS, embeddings, and jobs.
- Mount or wrap the legacy FastAPI application so current routes remain functional.
- Add an application factory and lifecycle hooks; do not move heavy model code yet.
- Add test fixtures that do not initialize Whisper or XTTS.

Gate:

- New app imports without loading heavy models.
- Health tests pass without MySQL or AI providers.
- Legacy route inventory remains registered.
- Existing backend authentication tests still pass.
- Current frontend production build still succeeds.

Rollback: continue starting `backend/main.py` directly.

### Phase 4 — PostgreSQL, SQLAlchemy, Alembic, and pgvector

Goal: introduce the V2 database alongside MySQL and make its schema reproducible.

Work:

- Add async SQLAlchemy 2 and an async PostgreSQL driver.
- Configure Alembic and enable the `vector` extension.
- Add UUID-based models for users, refresh tokens, conversations, messages, attachments, documents, document chunks, transcriptions, translations, voice profiles, memories, user preferences, vocabulary items, and activity logs.
- Add ownership, timestamps, soft-deletion where required, and relevant indexes.
- Store object keys rather than local absolute paths.
- Create an idempotent MySQL-to-PostgreSQL migration command.
- Preserve legacy IDs in mapping columns/tables during transition.
- Validate row counts, ownership, hashes, timestamps, and representative content.
- Dual-read only where necessary; avoid indefinite dual writes.

Migration order:

1. Schema and extensions
2. Users and preferences
3. Activity logs and permissions mapping
4. Audio records and speech recordings into transcriptions/attachments
5. TTS documents and jobs into documents/attachments
6. Voice records into consent-pending voice profiles
7. Validation report
8. Controlled read cutover

Gate:

- Alembic upgrade and downgrade succeed on an empty database.
- Migration dry run produces no destructive MySQL operations.
- User and content ownership validation passes.
- Legacy MySQL remains available for rollback.

Rollback: switch the database feature flag back to MySQL; no source rows are deleted.

### Phase 5 — Core chat

Goal: make conversation the primary backend domain.

Work:

- Implement conversation and message repositories/services.
- Add a provider-independent `LLMService` protocol.
- Add configured provider adapters and a deterministic fake for tests.
- Add EVA system behavior and language-aware response instructions.
- Add a conservative intent router for chat, translation, document Q&A, study, speech, and unsupported actions.
- Implement `/api/v1/conversations` and message endpoints.
- Stream assistant output using Server-Sent Events first; retain a non-streaming endpoint.
- Persist user and assistant messages with status and provider metadata.
- Do not automatically create durable memories from conversation text.

Gate:

- Users cannot access another user's conversations.
- Streaming disconnects and provider errors are handled.
- Intent routing has a deterministic fallback to ordinary chat.
- Provider-contract and API tests pass.

Rollback: disable the chat feature flag; legacy features remain independent.

### Phase 6 — Translation

Goal: unify English/Kinyarwanda translation behind one service.

Work:

- Extract existing NLLB behavior into `TranslationService`.
- Support automatic source-language detection with an explicit override.
- Add direct, natural, simple, professional, academic, and call-center modes.
- Preserve original text, detected language, requested mode, provider, and translated output.
- Allow the intent router and direct translation API to use the same service.
- Keep the legacy `/api/translate` adapter.

Gate:

- Unit tests cover both directions, every mode, empty input, oversized input, and provider failure.
- A bilingual evaluation set is reviewed for meaning preservation.
- Legacy request/response compatibility passes.

### Phase 7 — Document RAG

Goal: answer questions from user-owned documents with attributable retrieval.

Pipeline:

```text
upload -> validate -> store -> extract -> clean -> chunk
       -> embed -> pgvector -> retrieve -> answer with chunk citations
```

Work:

- Extract current PDF, DOCX, TXT, image, OCR, and audio-transcript parsing behind `DocumentService`.
- Add deterministic chunking with page/source metadata.
- Add an `EmbeddingService` protocol and dimension validation.
- Store vectors in `document_chunks`.
- Add owner-scoped semantic search and document Q&A.
- Return chunk/page citations with answers.
- Queue extraction, OCR, audio transcription, and embedding jobs.
- Track document and job state explicitly.

Gate:

- Cross-user retrieval tests pass.
- Reprocessing is idempotent.
- Failed jobs can retry without duplicate chunks.
- Answers include traceable source chunks.

### Phase 8 — Speech and TTS

Goal: preserve current speech capabilities behind cohesive abstractions.

Work:

- Extract `AudioPreprocessingService` and `TranscriptionService` from legacy code.
- Load Whisper models once per worker process through lifecycle-managed registries.
- Preserve raw transcript, corrected transcript, timestamps, model, and language metadata.
- Add automatic language detection with manual override.
- Introduce one `TTSService` that selects Edge TTS, gTTS, XTTS, or future providers.
- Move long audio and synthesis operations to Celery.
- Add job status and cancellation endpoints.
- Keep legacy audio/TTS endpoint adapters.
- Require authorized storage access for generated and uploaded audio.

Gate:

- Existing English and Kinyarwanda sample transcriptions are regression-tested.
- Models are not reloaded per request.
- Long requests do not block the FastAPI event loop.
- TTS fallback behavior is tested.

### Phase 9 — EVA memory

Goal: add explicit, user-controlled personal memory.

Work:

- Add proposed, approved, rejected, and deleted memory states.
- Store structured memory content plus embeddings.
- Retrieve only approved memories belonging to the active user.
- Add create, approve, edit, list, and delete APIs.
- Include provenance and last-used timestamps.
- Add limits, deduplication, retention rules, and sensitive-category exclusions.
- Never train or fine-tune a model automatically from user messages.

Gate:

- Unapproved memories never enter prompts.
- Cross-user retrieval and deletion tests pass.
- Users can inspect and permanently delete their memories.

### Phase 10 — Gradual Next.js frontend migration

Goal: introduce the conversational EVA UI without destroying the React SPA.

Migration layout:

```text
frontend/          # existing CRA application remains available
frontend-v2/       # Next.js App Router during transition
```

Work:

- Create Next.js, TypeScript, Tailwind, and shadcn/ui foundation.
- Add typed API client, TanStack Query, authentication/session handling, and environment-based API configuration.
- Build the application shell and central chat experience first.
- Add sidebar routes: New Chat, History, Translate, Study, Documents, Voice, Call Assistant, and Settings.
- Add message input with text, microphone, attachment, and send controls.
- Migrate feature routes one at a time.
- Use Zustand only for true client-side shared state; keep server state in TanStack Query.
- Route legacy users to the CRA application behind a deployment flag until parity is reached.

Gate:

- Chat works end to end on desktop and mobile layouts.
- Authentication and route protection work.
- Accessibility checks pass for primary workflows.
- Every migrated route has a parity checklist.

Rollback: route traffic back to the CRA deployment.

### Phase 11 — Study mode

Goal: compose existing document, chat, translation, and TTS services into learning workflows.

Work:

- Add structured outputs for summaries, short notes, explanations, quizzes, answers, flashcards, definitions, synonyms, and translations.
- Tie generated artifacts to conversations and source documents.
- Validate structured LLM output with Pydantic schemas.
- Add read-aloud through `TTSService`.
- Allow difficulty, language, audience, and length preferences.

Gate:

- Structured output validation and retry behavior pass.
- Generated questions and answers retain source references when based on documents.
- Study artifacts remain owner-scoped.

### Phase 12 — Consent-based voice profiles

Goal: replace permissive voice registration with an auditable, user-owned workflow.

Work:

- Explain risks and capture a versioned consent assertion.
- Require users to confirm ownership or authorization.
- Validate duration, signal quality, speaker count where practical, and supported format.
- Encrypt/restrict reference assets through the storage layer.
- Record consent time, purpose, status, and revocation.
- Allow export and permanent deletion.
- Restrict profile use to its owner unless an explicit administrative product requirement is approved.
- Remove celebrity/impersonation-oriented options.

Gate:

- Voice cloning cannot run without active consent.
- Revoked/deleted profiles cannot be synthesized.
- Access and deletion tests pass.

### Phase 13 — Call-center foundation

Goal: prepare real-time assistance without overbuilding telephony.

Work:

- Add authenticated WebSocket sessions.
- Define events for audio chunks, partial transcript, final transcript, translation, reply suggestion, sentiment cue, summary, action item, error, and heartbeat.
- Add bounded buffering, backpressure, disconnect cleanup, and session ownership.
- Reuse transcription, translation, LLM, and summary services.
- Add an internal simulated-audio client before integrating telephony providers.

Gate:

- Connection authentication and ownership tests pass.
- Reconnect and backpressure behavior is documented and tested.
- No separate call-center AI stack duplicates core EVA services.

## Cross-cutting work

### Security

Security corrections begin in Phase 3 and continue throughout:

- Replace unauthenticated password reset with expiring one-time tokens.
- Stop returning or emailing plaintext passwords.
- Require production secrets and validate configuration at startup.
- Add rotating hashed refresh tokens and server-side revocation.
- Protect stored media with authenticated authorization checks or short-lived signed URLs.
- Disable debug endpoints outside development.
- Validate OAuth state/nonce and consider PKCE.
- Add upload type, size, duration, and quota controls.
- Add rate limiting at the deployment boundary and sensitive endpoints.

### Observability

- Structured JSON logs with request/job correlation IDs
- Health, readiness, and dependency diagnostics
- Metrics for latency, model inference, queue depth, failures, and provider usage
- Audit records for administrative, memory, document, and voice actions
- No raw secrets, passwords, tokens, or private document content in logs

### Testing strategy

- Unit tests for service and domain rules
- Repository tests against temporary PostgreSQL
- API integration tests with dependency overrides
- Contract tests for AI, storage, and job providers
- Security tests for ownership and authorization matrices
- Migration tests with representative anonymized fixtures
- Frontend component and route tests
- End-to-end tests for chat, translation, documents, speech, and voice consent
- Small bilingual golden datasets for English/Kinyarwanda regression testing

## Dependency order

```text
Backend foundation
  -> PostgreSQL models and migrations
    -> Conversations and core chat
      -> Translation integration
      -> Document RAG
      -> Speech/TTS services
      -> Memory
        -> Next.js feature migration
          -> Study mode
          -> Voice profiles
          -> Call-center WebSockets
```

Redis/Celery and storage abstractions should be introduced no later than Document RAG, before expensive document/audio operations are exposed through V2.

## Major risks and mitigations

| Risk | Mitigation |
|---|---|
| Regression while splitting `main.py` | Characterization tests first; legacy adapters; one capability per change |
| MySQL/PostgreSQL divergence | One controlled migration command, validation reports, short transition window |
| Duplicate heavy model memory | Dedicated worker queues and process-level model registry |
| Poor Kinyarwanda output quality | Curated bilingual evaluation set, human review, provider fallback |
| RAG data leakage | Owner constraints in repository APIs and adversarial cross-user tests |
| Voice misuse | Explicit consent states, owner-only access, audit logs, deletion enforcement |
| Frontend migration stalls | Deploy CRA and Next.js in parallel; migrate route by route |
| Provider lock-in | Protocols, normalized request/response models, contract tests |
| Queue operational complexity | One Redis/Celery deployment and purpose-specific queues, not microservices |
| Scope expansion | Phase gates and explicit approval before each phase |

## Definition of done for each phase

A phase is complete only when:

1. Its scoped functionality is implemented.
2. Existing relevant behavior still works.
3. Automated checks pass or known failures are documented and accepted.
4. Security and ownership checks for the phase pass.
5. Configuration and migration instructions are documented.
6. The repository has a clean, reviewable commit.
7. The next phase has not begun without explicit approval.

## Exact Phase 3 scope

Phase 3 should change only foundation-level files. It must not yet migrate MySQL data, add chat, replace the frontend, or move the existing speech implementations.

Proposed additions:

```text
backend/app/__init__.py
backend/app/main.py
backend/app/api/__init__.py
backend/app/api/router.py
backend/app/api/v1/__init__.py
backend/app/api/v1/router.py
backend/app/api/v1/endpoints/__init__.py
backend/app/api/v1/endpoints/health.py
backend/app/core/__init__.py
backend/app/core/config.py
backend/app/core/errors.py
backend/app/core/logging.py
backend/app/schemas/__init__.py
backend/app/schemas/common.py
backend/app/services/__init__.py
backend/app/services/protocols.py
backend/tests/unit/test_config.py
backend/tests/integration/test_health.py
```

Possible small compatibility edits:

- `backend/main.py`: expose the legacy app for mounting without changing endpoints.
- `backend/requirements.txt`: add foundation dependencies and testing packages.
- `.env.example`: document validated settings.
- `README.md`: document the new optional entry point.

Phase 3 explicitly excludes PostgreSQL, Alembic models, chat implementation, Redis/Celery, model extraction, and frontend migration. Those remain in their assigned later phases.
