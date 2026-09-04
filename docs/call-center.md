# Call Assistant real-time foundation

Phase 13 adds the transport and session architecture for call-center assistance without coupling EVA to a telephony provider or running heavy speech models inside the web process.

## Connection flow

1. An authenticated client posts language configuration to `POST /api/v1/calls/tickets`.
2. EVA returns a signed, one-time, 60-second WebSocket ticket.
3. The client connects to `/api/v1/calls/ws?ticket=...`.
4. The server validates and consumes the ticket, confirms the UUID user is active, persists an owner-scoped session, and emits `session_ready`.

Tickets cannot be replayed. The in-process replay cache removes expired identifiers. Deployments with multiple web replicas should replace this cache with Redis while retaining the ticket interface.

## Events

Client events: `heartbeat`, `audio_chunk`, `end_audio`, `text_turn`, and `end_call`.

Server events: `session_ready`, `heartbeat`, `audio_ack`, `audio_buffered`, `final_transcript`, `translation`, `reply_suggestion`, `sentiment_cue`, `call_summary`, and `error`.

Audio chunks are base64 encoded, limited to 64 KiB each, held in a bounded queue, capped by total buffered bytes, and cleared after use or disconnect. Backpressure produces a retryable `call_backpressure` error. Phase 13 deliberately does not claim live STT: `end_audio` confirms that the buffer is ready for a future worker. The internal Next.js simulator follows with a declared text turn to exercise downstream intelligence.

Text turns reuse EVA language detection, NLLB translation, and provider-independent LLM reply guidance. Completed sessions retain transcript metadata, conservative sentiment cues, a summary, and action items. Session reads remain owner-scoped.

## Local simulation

Open `/calls` in `frontend-v2`, choose languages, and start a session. You can type a customer turn or send the built-in simulated Kinyarwanda audio turn. No microphone permission or telephony account is needed.

This foundation is not a production call recorder. Before telephony integration, move ticket replay tracking and connection coordination to Redis, define recording-consent requirements for the target jurisdiction, and connect buffered audio to the dedicated speech worker.
