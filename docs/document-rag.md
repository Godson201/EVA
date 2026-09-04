# EVA V2 Document Intelligence and RAG

Phase 7 adds an asynchronous, owner-scoped document pipeline:

```text
validate -> store -> queue -> extract -> clean -> chunk
         -> multilingual E5 embeddings -> pgvector -> retrieve -> cited answer
```

## Supported uploads

- PDF
- DOCX
- UTF-8 TXT
- PNG, JPEG, and TIFF images through Tesseract OCR

Uploads are limited by `EVA_MAX_DOCUMENT_BYTES` (25 MiB by default). EVA checks MIME type, filename extension, and file signature before storage. Object keys are namespaced by user UUID. Processing failures are recorded with retryable Celery job state.

## Storage

`EVA_STORAGE_BACKEND=local` stores development objects below `EVA_STORAGE_LOCAL_ROOT`. Set it to `s3` and configure the documented `EVA_S3_*` values for AWS S3, Cloudflare R2, or MinIO-compatible storage.

## Background processing

Start PostgreSQL and Redis:

```powershell
docker compose up -d postgres redis
```

Apply migrations and start the document worker from `backend`:

```powershell
alembic upgrade head
celery -A app.worker.celery_app worker -Q documents --loglevel=INFO
```

The first embedding job downloads `intfloat/multilingual-e5-base`. The model is retained once per worker process. Retrieval uses the model's required `passage:` and `query:` prefixes and cosine distance.

## API

- `POST /api/v1/documents` — validate, store, and queue a document
- `GET /api/v1/documents` — list the current user's documents
- `GET /api/v1/documents/{id}` — inspect processing state
- `GET /api/v1/documents/jobs/{id}` — inspect a processing job
- `POST /api/v1/documents/search` — semantic search
- `POST /api/v1/documents/ask` — document Q&A with sources
- `POST /api/v1/documents/{id}/summary` — cited document summary

Search always joins chunks through an owner-filtered document query. Document Q&A instructs the LLM to use only retrieved passages and returns the exact source chunks with document, chunk, page, and relevance metadata.

Audio lecture ingestion remains assigned to the speech refactor in Phase 8. Existing legacy document endpoints remain unchanged.
