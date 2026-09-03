# EVA V2 Database Migration

Phase 4 introduces PostgreSQL in parallel with the existing MySQL database. It does not modify or delete legacy rows.

## Start PostgreSQL with pgvector

```powershell
docker compose up -d postgres
```

Set `EVA_DATABASE_URL` for non-default credentials. The application requires an async PostgreSQL URL such as `postgresql+asyncpg://...`.

## Apply the V2 schema

```powershell
cd backend
alembic upgrade head
```

Rollback the Phase 4 schema:

```powershell
alembic downgrade base
```

Rollback removes V2 PostgreSQL tables. It never affects the legacy MySQL database.

## Legacy migration dry run

The migration command defaults to read-only dry-run mode:

```powershell
cd backend
python -m app.migration.legacy_mysql --report migration-report.json
```

Review source counts, skipped ownerless rows, and warnings before writing anything. To populate PostgreSQL after applying Alembic:

```powershell
python -m app.migration.legacy_mysql --apply --report migration-report.json
```

Writes are idempotent. Stable UUIDs and legacy source identifiers allow a run to be repeated. Existing MySQL rows are only selected, never updated or deleted.

Phase 4 migrates users, `audio_records`, and `speech_recordings`. Other legacy TTS/document/voice tables remain in MySQL until their service-specific phases define consent and storage semantics. This prevents unsafe copying of voice samples before Phase 12 consent controls exist.

## Validation before cutover

1. Compare the report's source and written counts.
2. Resolve every ownerless-row warning.
3. Confirm a sample of user password hashes was preserved exactly.
4. Confirm every migrated transcription belongs to the correct UUID user.
5. Confirm attachment object keys point to the planned storage import location.
6. Keep `EVA_LEGACY_APP_ENABLED=False`; Phase 4 does not switch production reads.

No MySQL read cutover is authorized in Phase 4. PostgreSQL becomes the primary application store only in a later approved phase after repository and authentication services are implemented.
