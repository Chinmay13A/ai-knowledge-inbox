import asyncio
import sqlite3

import numpy as np
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.ai.embeddings.base import UnconfiguredEmbedder
from app.db import connect
from app.errors import EmbeddingError
from app.services.embedding_service import embed_item, embed_pending
from app.services.vectors import from_blob
from tests.conftest import FakeEmbedder, add_note


def db(app: FastAPI) -> sqlite3.Connection:
    return connect(app.state.settings.db_path)


def item(client: TestClient, item_id: int) -> dict:
    return next(i for i in client.get("/items").json()["items"] if i["id"] == item_id)


def test_ingest_returns_pending_then_item_becomes_ready(client: TestClient, app: FastAPI, embedder: FakeEmbedder) -> None:
    created = add_note(client, "Vector search finds chunks by meaning.\nIt powers RAG.")

    assert created["status"] == "pending"  # the response is sent before embedding runs
    assert item(client, created["id"])["status"] == "ready"
    assert item(client, created["id"])["error"] is None
    conn = db(app)
    rows = conn.execute("SELECT embedding, embedding_model FROM chunks WHERE item_id = ?", (created["id"],)).fetchall()
    conn.close()
    assert rows and all(row["embedding_model"] == embedder.model_id for row in rows)
    assert all(from_blob(row["embedding"]).shape == (embedder.dimensions,) for row in rows)


def test_embedding_failure_marks_item_failed(client: TestClient, embedder: FakeEmbedder) -> None:
    embedder.error = EmbeddingError("Gemini rate limit reached, try again shortly")

    created = add_note(client, "This note cannot be embedded right now.")

    listed = item(client, created["id"])
    assert listed["status"] == "failed"
    assert listed["error"] == "Gemini rate limit reached, try again shortly"
    assert listed["chunk_count"] == 1  # content and chunks are kept for a later retry


def test_unexpected_error_is_stored_generically(client: TestClient, embedder: FakeEmbedder) -> None:
    embedder.error = RuntimeError("socket exploded at 0xdeadbeef")

    created = add_note(client, "Unexpected failure.")

    assert item(client, created["id"])["error"] == "Embedding failed due to an unexpected error"


def test_missing_api_key_fails_with_configuration_message(app: FastAPI) -> None:
    app.state.embedder = UnconfiguredEmbedder()

    with TestClient(app) as client:
        created = add_note(client, "No key configured.")
        listed = item(client, created["id"])

    assert listed["status"] == "failed"
    assert "set EMBEDDING_API_KEY" in listed["error"]


def test_already_embedded_chunks_are_skipped(client: TestClient, app: FastAPI, embedder: FakeEmbedder) -> None:
    created = add_note(client, "Embed me once.")
    calls_before = len(embedder.document_calls)

    outcome = asyncio.run(embed_item(app.state.settings.db_path, embedder, created["id"]))

    assert outcome.ok and outcome.chunks_embedded == 0
    assert len(embedder.document_calls) == calls_before


def test_model_change_triggers_re_embedding(client: TestClient, app: FastAPI) -> None:
    created = add_note(client, "Switch providers later.")
    new_model = FakeEmbedder(dimensions=32, model_id="fake:hash@32")

    items, chunks, failed = asyncio.run(embed_pending(app.state.settings.db_path, new_model))

    assert (items, chunks, failed) == (1, 1, 0)
    conn = db(app)
    row = conn.execute("SELECT embedding, embedding_model FROM chunks WHERE item_id = ?", (created["id"],)).fetchone()
    conn.close()
    assert row["embedding_model"] == "fake:hash@32"
    assert from_blob(row["embedding"]).shape == (32,)


def test_backfill_retries_failed_items(client: TestClient, app: FastAPI, embedder: FakeEmbedder) -> None:
    embedder.error = EmbeddingError("temporary outage")
    failed_item = add_note(client, "Failed the first time.")
    embedder.error = None

    items, chunks, failed = asyncio.run(embed_pending(app.state.settings.db_path, embedder))

    assert (items, failed) == (1, 0) and chunks == 1
    assert item(client, failed_item["id"])["status"] == "ready"
    assert item(client, failed_item["id"])["error"] is None


def test_similar_texts_get_similar_vectors(embedder: FakeEmbedder) -> None:
    rag, rag_question, groceries = (
        embedder.vector(text)
        for text in ("retrieval augmented generation uses retrieval", "what is retrieval augmented generation", "buy milk and eggs")
    )

    assert float(np.dot(rag, rag_question)) > float(np.dot(groceries, rag_question))
