# EVA personal memory

Phase 9 adds an explicit, user-controlled memory layer. EVA does not train or fine-tune models from conversations and does not silently save chat content.

## Consent lifecycle

1. `POST /api/v1/memories` creates a `proposed` memory without an embedding.
2. The user inspects it and calls `POST /api/v1/memories/{id}/approve`.
3. Approval creates the embedding and permits retrieval for that user only.
4. Editing an approved memory returns it to `proposed` and removes its embedding until it is approved again.
5. Rejection excludes it from retrieval; `DELETE` permanently removes the database row and vector.

Supported categories are preferences, terminology, vocabulary, corrections, profession, explanation style, and approved phrases. Passwords, access tokens, identity-number patterns, and payment-card patterns are rejected. Configuration limits item count, content length, retrieval count, and maximum retention.

## Retrieval

Chat queries pgvector only when the active user has an approved, unexpired memory. Retrieved values are added as untrusted profile context, not instructions, and `last_used_at` is updated. Repository predicates enforce user ownership and approval before vector ranking.

## API

- `POST /api/v1/memories`
- `GET /api/v1/memories?status=proposed|approved|rejected|deleted`
- `GET /api/v1/memories/{id}`
- `PUT /api/v1/memories/{id}`
- `POST /api/v1/memories/{id}/approve`
- `POST /api/v1/memories/{id}/reject`
- `DELETE /api/v1/memories/{id}`

Run `alembic upgrade head` before enabling the endpoints. Deleting a memory is intentionally permanent; restore requires creating and approving a new proposal.
