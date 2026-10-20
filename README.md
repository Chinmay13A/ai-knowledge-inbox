# AI Knowledge Inbox

A small web app to save notes and URLs, then ask questions about them. Answers come from a simple RAG pipeline (chunk → embed → retrieve → LLM) and cite their sources.

> Work in progress — built step by step, one feature per commit.

## Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.10+, FastAPI, Pydantic |
| Storage | SQLite (items, chunks, embedding vectors) |
| AI | Provider-agnostic layer; default: Google Gemini (free tier) embeddings |
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
# put a free Gemini key in .env:  EMBEDDING_API_KEY=...   (https://aistudio.google.com/apikey)
uvicorn app.main:app --reload --port 8000
```

Without a key the app still runs; new items just end up `failed` with a message telling you to set it.

- API docs (Swagger): http://localhost:8000/docs
- Health check: http://localhost:8000/health
- Tests: `pytest`
- Backfill / retry: `python -m app.scripts.reindex` chunks items that have no chunks and embeds every item that is `pending`, `failed`, or embedded with a different model. Safe to run any time.

Configuration lives in `backend/.env` (see `.env.example`): log level, CORS origins, DB path, URL fetch limits, `RESPECT_ROBOTS_TXT`, chunking (`CHUNK_SIZE_CHARS`, `CHUNK_OVERLAP_CHARS`) and embeddings (`EMBEDDING_*`). Invalid values fail at startup with a clear message.

### Switching AI providers

The code only talks to an `Embedder` interface; the provider is picked from `.env`. After switching, run `python -m app.scripts.reindex` to re-embed everything with the new model (vectors from different models are never mixed).

```env
# Google Gemini (default, free tier)
EMBEDDING_PROVIDER=gemini
EMBEDDING_MODEL=gemini-embedding-001
EMBEDDING_DIMENSIONS=768
EMBEDDING_API_KEY=<your Gemini key>
```

```env
# OpenAI
EMBEDDING_PROVIDER=openai_compatible
EMBEDDING_BASE_URL=https://api.openai.com/v1
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=768
EMBEDDING_API_KEY=<your OpenAI key>
```

```env
# Local Ollama (free, offline; run `ollama pull nomic-embed-text` first)
EMBEDDING_PROVIDER=openai_compatible
EMBEDDING_BASE_URL=http://localhost:11434/v1
EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_DIMENSIONS=
EMBEDDING_API_KEY=
```

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
  "chunk_count": 1,
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
- **Processing is asynchronous.** The response comes back immediately with `status: "pending"`; embedding runs in a background task right after. Poll `GET /items` until the item is `ready`, or `failed` with a human-readable `error` (e.g. a missing or rejected API key, or a provider rate limit). Failed items keep their content and chunks; fix the cause and run `python -m app.scripts.reindex`.

### `GET /items` — list saved items

```bash
curl "http://localhost:8000/items?limit=50&offset=0"
```

`200 OK` — newest first; `preview` is the first 200 characters of the content.

```json
{ "items": [ { "id": 1, "source_type": "note", "...": "..." } ], "total": 1, "limit": 50, "offset": 0 }
```

`limit` is 1–200 (default 50), `offset` ≥ 0. Each item includes `chunk_count`.

### `GET /items/{id}/chunks` — inspect chunking (debugging aid)

Not one of the three required endpoints: it shows exactly what text will be embedded and retrieved for an item.

```bash
curl http://localhost:8000/items/2/chunks
```

```json
{ "item_id": 2, "chunks": [ { "index": 0, "text": "Retrieval-augmented generation ...", "chars": 732 }, "..." ] }
```

Unknown item → `404 item_not_found`.

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
| 404 | `item_not_found` | No item with that ID |
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
| Services | `app/services/` | Business logic and orchestration (ingestion, page fetching, chunking, embedding pipeline) |
| AI providers | `app/ai/` | Provider-agnostic interfaces (`Embedder`), one adapter per provider API, a factory that picks one from config, and shared HTTP retry/error handling |
| Repositories | `app/repositories/` | All SQL; return domain objects |
| Models | `app/models/` | Domain objects (`Item`, `Chunk`) and Pydantic request/response schemas |
| Cross-cutting | `app/errors.py`, `app/middleware.py`, `app/logging_config.py`, `app/db.py` | Error format, request context, logging, DB connection |
| Scripts | `app/scripts/` | Maintenance commands (e.g. `reindex` backfill) |

## Design decisions & tradeoffs

### Storage: SQLite
- One file, no extra infrastructure, and enough for a single-user inbox. WAL mode lets reads continue during a write.
- Plain `sqlite3` behind a small repository layer instead of an ORM: the schema is tiny, all SQL lives in one module, and moving to Postgres later only touches the repositories.
- One connection per request; schema is created on startup with `CREATE TABLE IF NOT EXISTS` (additive only, no migration tool needed yet).
- Two tables: `items` (raw content + metadata) and `chunks` (`item_id`, `chunk_index`, `text`, and an `embedding` column filled in by the embedding step). Chunks are deleted with their item (`ON DELETE CASCADE`).
- An item and its chunks are written in **one transaction**, so a failure can never leave an item without chunks (or orphan chunks). Repositories only run SQL; the service layer owns the transaction.
- **At scale:** SQLite allows one writer at a time, and the DB lives on a single machine. Production would use Postgres with a migration tool (e.g. Alembic).

### API
- `POST /ingest` takes one payload whose `type` field (`note` | `url`) decides which fields are required. One endpoint, but each shape is validated strictly.
- `GET /items` returns previews instead of full content to keep the list response small, and uses limit/offset paging. **At scale:** offset paging gets slow on deep pages, so switch to cursor-based paging (`?before=<id>`).

### Chunking strategy
Implemented in `app/services/chunker.py` as pure, deterministic functions. Defaults: **800 characters per chunk, 100 characters of overlap**.

1. Normalize whitespace and split the text into blocks on line breaks (paragraphs, list items, headings). Both notes and extracted web pages use line breaks as structure.
2. Keep each block whole if it fits; otherwise split it at **sentence** boundaries, and a sentence that's still too long at **word** boundaries. Only a single "word" longer than a chunk (e.g. a huge URL) is ever cut.
3. Greedily pack blocks/sentences into chunks of at most 800 characters.
4. Start each chunk with the last ≤100 characters of the previous one (snapped to a word boundary).

Why:
- **~800 characters (≈150–200 tokens, one or two paragraphs)** keeps each chunk focused on one idea, so retrieval is precise and the snippet shown as a citation is short enough to read. Much larger chunks dilute the embedding with unrelated content; much smaller ones lose context.
- **Respecting paragraph and sentence boundaries** keeps ideas intact; fixed-width slicing would cut sentences in half and produce confusing snippets.
- **Overlap** (~12% extra storage) means a fact that straddles a boundary still appears whole in at least one chunk.
- **Characters instead of tokens:** no tokenizer dependency, easy to reason about and test, and far below any embedding model's input limit (~4 characters per token).
- Example: the Wikipedia article on RAG (15,404 characters) becomes 28 chunks.

At scale / in production: size chunks in tokens using the embedding model's tokenizer; use heading-aware or semantic chunking (split where the topic changes); apply per-content-type strategies (code, tables); prefix chunks with the document title for extra context; store character offsets to highlight the exact passage in the source.

### Embeddings & vector storage
- **Providers behind an interface.** Services depend only on `Embedder` (`embed_documents`, `embed_query`, `model_id`). `app/ai/embeddings/factory.py` is the only code that knows concrete classes, so switching provider or model is a `.env` change. Two adapters cover most of the market: `gemini` and `openai_compatible` (OpenAI, Ollama, LM Studio, Together, Mistral, …). The answer-generating LLM (next step) follows the same pattern.
- **Plain REST over `httpx` instead of vendor SDKs:** no lock-in, one shared retry/backoff and error-message path (`app/ai/http.py`) for every provider, and fully offline tests with a mock transport. Keys travel in headers, are stored as `SecretStr`, and are never logged.
- **Default model: Gemini `gemini-embedding-001`** on the free tier (no cost), with retrieval task types: chunks are embedded as `RETRIEVAL_DOCUMENT` and questions as `RETRIEVAL_QUERY`, which Gemini optimizes for short-question-vs-passage search.
- **768 dimensions** instead of the default 3,072: about 4× less storage and faster similarity search, with little quality loss for short chunks.
- **Vectors are normalized to unit length**, so cosine similarity is a plain dot product at query time.
- **Stored as float32 BLOBs in the `chunks` table** (~3 KB per chunk) together with the `model_id` that produced them (`gemini:gemini-embedding-001@768`). If the provider, model or dimensions change, the backfill detects stale vectors and re-embeds them; vectors from different models are never compared.
- **Background processing:** `POST /ingest` stays fast and returns `pending`; a FastAPI background task embeds the chunks with its own DB connection, then writes all vectors and `status=ready` in one transaction (or `status=failed` + `error`). Already-embedded chunks are skipped, so retries cost nothing extra. The request ID is carried into the background task's logs.
- **Free-tier caveats:** per-minute/day rate limits (handled with retries, exponential backoff and `Retry-After`; the backfill embeds one item at a time), and content sent on the free tier may be used by Google to improve its products. For private data in production, use a paid tier, another provider, or a local model (config-only change).
- **At scale:** in-process background tasks are lost if the server restarts (items stay `pending` until the backfill runs); production would use a durable job queue (Celery/RQ/Arq) with a global rate limiter. A model change means re-embedding everything, which should run as a batch job. Storing vectors in SQLite is fine for thousands of chunks; beyond that, use a vector index (see retrieval).

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
