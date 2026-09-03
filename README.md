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
