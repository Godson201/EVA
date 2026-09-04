# EVA Study Mode

Phase 11 turns text and user-owned documents into durable, structured learning artifacts.

## Capabilities

`POST /api/v1/study/generate` supports `summary`, `key_points`, `short_notes`, `explanation`, `quiz`, `flashcards`, `vocabulary`, `synonyms`, and `translation`. Requests can set English or Kinyarwanda, beginner/intermediate/advanced difficulty, audience, short/medium/long output, and item count.

When a document is selected, EVA retrieves only chunks belonging to the active user. The model receives stable source labels, generated quiz/flashcard/vocabulary citations are restricted to those labels, and the artifact stores source excerpts plus chunk, document, and page identifiers.

AI responses are validated against Pydantic schemas. Invalid output receives one constrained retry and then returns a stable provider error instead of storing malformed data.

## Routes

- `POST /api/v1/study/generate`
- `GET /api/v1/study/artifacts`
- `GET /api/v1/study/artifacts/{id}`
- `DELETE /api/v1/study/artifacts/{id}`

Artifacts can optionally link to a conversation and document. All reads and deletes enforce ownership. The Next.js Study workspace composes the document API for sources and the Phase 8 speech synthesis API for read-aloud.

Apply `alembic upgrade head` before enabling Study Mode.
