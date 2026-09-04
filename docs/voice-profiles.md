# Consent-based voice profiles

Phase 12 replaces permissive voice registration with an auditable, owner-only workflow.

## Consent and safety

`GET /api/v1/voices/consent` returns the current disclosure version, voice-cloning risks, and required assertions. Registration requires the user to confirm ownership or explicit authorization, one consenting speaker, and lawful non-deceptive use. The server stores the exact assertion, version, purpose, and consent timestamp.

EVA does not offer celebrity voices or public profile sharing. Profiles are usable only by their owner, and Phase 8 synthesis checks that the profile is active, consented, and not revoked.

## Sample validation and storage

Supported formats are WAV, MP3, OGG, WebM, and M4A. Samples must be 5–60 seconds by default and pass loudness, clipping, and silence thresholds. Speaker uniqueness is recorded honestly as an owner attestation; EVA does not claim automated diarization.

New reference samples are encrypted client-side-of-storage with AES-256-GCM and object-key authenticated data before local or S3-compatible persistence. The normal storage API cannot transparently expose the plaintext. Existing legacy samples remain readable during migration and should be re-enrolled to gain encryption.

Use a stable, high-entropy `EVA_STORAGE_ENCRYPTION_KEY` in production. Changing it without re-encrypting samples makes existing encrypted profiles unreadable.

## API

- `GET /api/v1/voices/consent`
- `POST /api/v1/voices` — consented multipart enrollment
- `GET /api/v1/voices` — owner profile list
- `POST /api/v1/voices/{id}/revoke`
- `GET /api/v1/voices/{id}/export` — authenticated decrypted export
- `DELETE /api/v1/voices/{id}` — permanent profile and object deletion

The Next.js Voice workspace exposes disclosure, enrollment, quality guidance, export, revocation, and a separately confirmed permanent-delete action.
