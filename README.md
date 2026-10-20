# AI Knowledge Inbox

A small web app to save notes and URLs, then ask questions about them. Answers come from a simple RAG pipeline (chunk → embed → retrieve → LLM) and cite their sources.

> Work in progress — built step by step, one feature per commit.

## Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.10+, FastAPI, Pydantic |
| Storage | SQLite (items, chunks, embedding vectors) |
| AI | OpenAI embeddings + chat model |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS v4 |

## Project layout

```
backend/    FastAPI app (app/), tests (tests/)
frontend/   React + Vite app (src/)
```

## Running locally

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env         # macOS/Linux: cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

- API docs (Swagger): http://localhost:8000/docs
- Health check: http://localhost:8000/health
- Tests: `pytest`

### Frontend

```bash
cd frontend
npm install
copy .env.example .env         # macOS/Linux: cp .env.example .env
npm run dev
```

Open http://localhost:5173. The badge in the header shows whether the backend is reachable.

## API

Interactive docs: http://localhost:8000/docs

### `POST /ingest` — save a note

```bash
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"type": "note", "content": "Meeting notes: ship v1 by Friday"}'
```

`201 Created`

```json
{
  "id": 1,
  "source_type": "note",
  "title": "Meeting notes: ship v1 by Friday",
  "url": null,
  "status": "pending",
  "created_at": "2026-10-20T12:00:00+00:00",
  "preview": "Meeting notes: ship v1 by Friday"
}
```

- `type` selects the payload shape: `note` needs `content` (non-blank, max 50,000 chars); `url` needs `url`.
- The title of a note is its first non-empty line (max 80 chars).
- `status` is `pending` until the item has been embedded for search.

### `GET /items` — list saved items

```bash
curl "http://localhost:8000/items?limit=50&offset=0"
```

`200 OK` — newest first; `preview` is the first 200 characters of the content.

```json
{ "items": [ { "id": 1, "source_type": "note", "...": "..." } ], "total": 1, "limit": 50, "offset": 0 }
```

`limit` is 1–200 (default 50), `offset` ≥ 0.

### Errors

Every error uses the same shape:

```json
{
  "error": {
    "code": "validation_error",
    "message": "content: must not be blank",
    "details": [{ "field": "content", "message": "must not be blank" }],
    "request_id": "2ba8c96db2b840dc9bd7ad6e82763ade"
  }
}
```

| Status | `code` | When |
|---|---|---|
| 400 | `invalid_json` | Request body is not valid JSON |
| 404 / 405 | `http_error` | Unknown route or wrong method |
| 422 | `validation_error` | Body or query parameters fail validation |
| 500 | `internal_error` | Unexpected server error (details are only in the logs) |
| 501 | `not_implemented` | Feature not available yet |

## Observability

- Every log line is a single JSON object (`ts`, `level`, `logger`, `message`, plus context fields such as `item_id`).
- Every request gets an `X-Request-ID` (an incoming one is reused, otherwise generated). It is returned in the response header and in error bodies, and is attached automatically to **every** log line written while handling that request, so one request can be traced end to end.
- Each request ends with a `request.completed` line containing `method`, `path`, `status_code` and `duration_ms`. Unhandled exceptions are logged with a stack trace as `request.failed`.

## Code structure (backend)

| Layer | Folder | Responsibility |
|---|---|---|
| API | `app/api/` | HTTP only: validate input, call a service, shape the response |
| Services | `app/services/` | Business logic and orchestration (e.g. ingestion) |
| Repositories | `app/repositories/` | All SQL; return domain objects |
| Models | `app/models/` | `Item` domain object and Pydantic request/response schemas |
| Cross-cutting | `app/errors.py`, `app/middleware.py`, `app/logging_config.py`, `app/db.py` | Error format, request context, logging, DB connection |

## Design decisions & tradeoffs

### Storage: SQLite
- One file, no extra infrastructure, and enough for a single-user inbox. WAL mode lets reads continue during a write.
- Plain `sqlite3` behind a small repository layer instead of an ORM: the schema is tiny, all SQL lives in one module, and moving to Postgres later only touches the repositories.
- One connection per request; schema is created on startup with `CREATE TABLE IF NOT EXISTS` (additive only, no migration tool needed yet).
- **At scale:** SQLite allows one writer at a time, and the DB lives on a single machine. Production would use Postgres with a migration tool (e.g. Alembic).

### API
- `POST /ingest` takes one payload whose `type` field (`note` | `url`) decides which fields are required. One endpoint, but each shape is validated strictly.
- `GET /items` returns previews instead of full content to keep the list response small, and uses limit/offset paging. **At scale:** offset paging gets slow on deep pages, so switch to cursor-based paging (`?before=<id>`).
