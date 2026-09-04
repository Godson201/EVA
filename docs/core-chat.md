# EVA V2 Core Chat

Phase 5 adds owner-scoped conversations and messages under `/api/v1/conversations`.

## Configuration

```env
EVA_LLM_PROVIDER=anthropic
EVA_ANTHROPIC_API_KEY=your-key
EVA_ANTHROPIC_MODEL=claude-sonnet-5
EVA_LLM_TIMEOUT_SECONDS=60
```

For Groq development access, use:

```env
EVA_LLM_PROVIDER=groq
EVA_GROQ_API_KEY=your-key
EVA_GROQ_MODEL=openai/gpt-oss-20b
```

Provider selection is isolated behind the `LLMService` contract. Tests use a deterministic provider and never call an external API.

## Endpoints

- `POST /api/v1/conversations`
- `GET /api/v1/conversations`
- `GET /api/v1/conversations/{conversation_id}`
- `DELETE /api/v1/conversations/{conversation_id}`
- `POST /api/v1/conversations/{conversation_id}/messages`
- `POST /api/v1/conversations/{conversation_id}/messages/stream`

The streaming endpoint uses Server-Sent Events with `delta`, `done`, and `error` event types. Messages are stored in PostgreSQL. Every lookup includes the authenticated user's UUID so another user's conversation is returned as not found.

V2 bearer tokens must contain a PostgreSQL user UUID in the `sub` claim and be signed with `EVA_SECRET_KEY`. Token issuance and rotating refresh-token flows are part of the later authentication modernization work; Phase 5 does not weaken authentication by adding a temporary bypass.

The intent router deliberately falls back to normal chat when uncertain. Translation, document Q&A, study, and speech execution are not implemented in this phase; recognized intents are stored so their dedicated phases can connect the appropriate services.
