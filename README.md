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

### `POST /ingest` — save a note or URL

**Note**

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

**URL** — the server fetches the page and stores its readable main text:

```bash
curl -X POST http://localhost:8000/ingest   -H "Content-Type: application/json"   -d '{"type": "url", "url": "https://en.wikipedia.org/wiki/Retrieval-augmented_generation"}'
```

`201 Created` with `"source_type": "url"`, the page `title`, the final `url` (after redirects) and a `preview` of the extracted text.

- `type` selects the payload shape: `note` needs `content` (non-blank, max 50,000 chars); `url` needs an `http`/`https` `url`.
- A note's title is its first non-empty line (max 80 chars); a URL's title is the page title (falling back to the first line of its text).
- If fetching fails, nothing is stored and an error explains why (see below).
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
| 422 | `url_not_allowed` | URL points to a private/internal address, or its host can't be resolved |
| 422 | `blocked_by_robots` | The site's robots.txt disallows automated access to that page |
| 422 | `unsupported_content` | Not an HTML or plain-text page (e.g. PDF), or larger than 5 MB |
| 422 | `empty_content` | No readable text found on the page (e.g. JavaScript-only pages) |
| 500 | `internal_error` | Unexpected server error (details are only in the logs) |
| 502 | `url_fetch_failed` | Site unreachable, too many redirects, or it responded with an error status |
| 504 | `url_fetch_timeout` | Site didn't respond within 10 s |

## Observability

- Every log line is a single JSON object (`ts`, `level`, `logger`, `message`, plus context fields such as `item_id`).
- Every request gets an `X-Request-ID` (an incoming one is reused, otherwise generated). It is returned in the response header and in error bodies, and is attached automatically to **every** log line written while handling that request, so one request can be traced end to end.
- Each request ends with a `request.completed` line containing `method`, `path`, `status_code` and `duration_ms`. Unhandled exceptions are logged with a stack trace as `request.failed`.

## Code structure (backend)

| Layer | Folder | Responsibility |
|---|---|---|
| API | `app/api/` | HTTP only: validate input, call a service, shape the response |
| Services | `app/services/` | Business logic and orchestration (ingestion, page fetching) |
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

### Ingestion: URLs
- **Fetched on the server** with async `httpx`, so a slow site doesn't block other requests. Limits: 10 s timeout, 5 redirects, 5 MB per page, 100,000 characters of extracted text.
- **Text extraction with [trafilatura](https://trafilatura.readthedocs.io/)** rather than hand-written BeautifulSoup rules: it is built to find the main content of arbitrary pages and drop navigation, ads and footers. For very short pages it falls back to all visible text.
- **We store the extracted text, not the raw HTML.** It's what search and answers need, and it is far smaller. The original is always one click away via the stored URL.
- **SSRF protection:** because the server fetches user-supplied URLs, every request (including every redirect hop) is checked: only `http`/`https`, and the host must resolve only to public IP addresses. This blocks `localhost`, private networks and cloud metadata endpoints like `169.254.169.254`. *Known gap:* the DNS check and the actual connection are separate lookups, so a DNS-rebinding attack could slip between them. Production would pin the resolved IP or send fetches through an egress proxy.
- **No JavaScript rendering:** single-page apps may return little or no text (`empty_content`). Production could render such pages with a headless browser.
- **Duplicates** of the same URL are currently allowed.
- **At scale:** the fetch happens inside the request, so the client waits (up to 10 s). Production would queue ingestion as background jobs and report progress through the item's `status`.

### Responsible fetching
- The app fetches **only the single URL a user submits**, once. It never crawls, follows links or fetches in bulk.
- It identifies itself honestly with the User-Agent `AIKnowledgeInbox/0.1`.
- **robots.txt is respected by default** (`RESPECT_ROBOTS_TXT=true`): before fetching a page, the site's `/robots.txt` is read with Python's `urllib.robotparser`, and the request is refused (`blocked_by_robots`) if our bot is disallowed. The page itself is then never downloaded.
  - A missing robots.txt (4xx) means no restrictions, per RFC 9309.
  - If robots.txt is temporarily unavailable (5xx, timeout), we deliberately proceed and log `fetch.robots_unavailable`, because this is a one-off fetch requested by a user, not a crawler. RFC 9309 would treat 5xx as "disallow all"; that stricter choice is a one-line change.
  - It is configurable because user-initiated fetchers (read-later apps) commonly don't apply crawler rules; the default errs on the side of respecting site owners.
- Only publicly accessible pages are fetched; no logins, paywalls or CAPTCHAs are bypassed.
- Stored text is used only for the single user's own questions, and answers link back to the source.
- Terms of service can't be checked automatically; a public multi-user deployment would need a policy for that.
