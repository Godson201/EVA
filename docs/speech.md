# Speech processing

Phase 8 adds asynchronous audio transcription and speech synthesis to the modular EVA API. The original speech routes remain available through legacy compatibility mode while clients migrate.

## Architecture

- Uploads are validated by MIME type, filename extension, size, and file signature before storage.
- Audio is decoded at 16 kHz mono, normalized, and noise-reduced when `noisereduce` is installed.
- Whisper models are loaded lazily inside the speech worker. English uses `openai/whisper-small`; Kinyarwanda uses `pacomesimon/whisper-small-rw` by default.
- Automatic detection performs an English first pass and uses EVA's deterministic English/Kinyarwanda detector; a detected Kinyarwanda result is retranscribed with the specialized model. Clients can override this with `en` or `rw`.
- TTS uses an optional active, consented XTTS voice profile, then Edge TTS, then gTTS. Kinyarwanda currently uses a clearly labelled Swahili voice fallback because those engines do not offer a native Kinyarwanda voice.
- Stored audio is never publicly mounted. Downloads require authentication and ownership.

## Routes

- `POST /api/v1/speech/transcriptions` — multipart audio upload; optional `language=auto|en|rw`
- `GET /api/v1/speech/transcriptions` — list the current user's transcripts
- `GET /api/v1/speech/transcriptions/{id}` — transcript text, timestamps, model, and status
- `POST /api/v1/speech/synthesize` — queue English or Kinyarwanda speech
- `GET /api/v1/speech/jobs/{id}` — inspect transcription or synthesis progress
- `GET /api/v1/speech/attachments/{id}` — owner-authorized audio download

## Worker

Apply migrations, start Redis, then run the dedicated queue:

```powershell
cd backend
alembic upgrade head
celery -A app.worker.celery_app worker -Q speech --loglevel=INFO
```

Production workers should have FFmpeg available for compressed audio decoding. Tune `EVA_MAX_AUDIO_BYTES` and model settings from `.env.example` according to available memory and GPU capacity.
