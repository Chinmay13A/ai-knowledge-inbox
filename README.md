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

## Observability

- Every log line is a single JSON object (`ts`, `level`, `logger`, `message`, plus context fields).
- Every request gets an `X-Request-ID` (an incoming one is reused, otherwise generated). It is returned in the response header and included in the request's log line together with `method`, `path`, `status_code` and `duration_ms`.

## Design decisions & tradeoffs

_Filled in as each step is built._
