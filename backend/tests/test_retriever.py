import asyncio
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest

from app.ai.embeddings.base import UnconfiguredEmbedder
from app.db import connect, init_db
from app.errors import AINotConfiguredError
from app.models.chunk import Chunk, RetrievedChunk
from app.repositories import chunks_repo, items_repo
from app.services.retriever import retrieve
from app.services.vectors import to_blob
from tests.conftest import FakeEmbedder

NOTES = {
    "rag": "Retrieval augmented generation retrieves relevant chunks and passes them to the language model.",
    "groceries": "Buy milk, eggs, bread and coffee on the way home.",
    "travel": "Train to Pune leaves at nine; pack a charger and an umbrella.",
}


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    db_path = str(tmp_path / "retrieval.db")
    init_db(db_path)
    connection = connect(db_path)
    yield connection
    connection.close()


def add_embedded(conn: sqlite3.Connection, embedder: FakeEmbedder, title: str, text: str, url: str | None = None) -> int:
    with conn:
        item = items_repo.create_item(conn, source_type="url" if url else "note", title=title, content=text, url=url)
        chunks_repo.insert_chunks(conn, item.id, [Chunk(index=0, text=text)])
        chunk = chunks_repo.list_chunks(conn, item.id)[0]
        chunks_repo.set_embeddings(conn, [(chunk.id, embedder.vector(text))], embedder.model_id)
    return item.id


def search(conn: sqlite3.Connection, embedder, query: str, top_k: int = 5, min_score: float = -1.0) -> list[RetrievedChunk]:  # noqa: ANN001
    return asyncio.run(retrieve(conn, embedder, query, top_k=top_k, min_score=min_score))


@pytest.fixture
def inbox(conn: sqlite3.Connection, embedder: FakeEmbedder) -> dict[str, int]:
    return {name: add_embedded(conn, embedder, name.title(), text) for name, text in NOTES.items()}


def test_most_relevant_chunk_ranks_first(conn, embedder, inbox) -> None:  # noqa: ANN001
    results = search(conn, embedder, "how does retrieval augmented generation work")

    assert results[0].item_id == inbox["rag"]
    assert results[0].score > results[1].score
    assert [r.score for r in results] == sorted((r.score for r in results), reverse=True)


def test_top_k_limits_results(conn, embedder, inbox) -> None:  # noqa: ANN001
    assert len(search(conn, embedder, "milk eggs", top_k=2)) == 2
    assert len(search(conn, embedder, "milk eggs", top_k=10)) == 3


def test_min_score_drops_weak_matches(conn, embedder, inbox) -> None:  # noqa: ANN001
    results = search(conn, embedder, "buy milk eggs bread coffee", min_score=0.5)

    assert [r.item_id for r in results] == [inbox["groceries"]]


def test_result_carries_source_details(conn, embedder) -> None:  # noqa: ANN001
    item_id = add_embedded(conn, embedder, "RAG article", NOTES["rag"], url="https://example.com/rag")

    result = search(conn, embedder, "retrieval augmented generation")[0]

    assert (result.item_id, result.item_title, result.item_url, result.source_type, result.chunk_index) == (
        item_id,
        "RAG article",
        "https://example.com/rag",
        "url",
        0,
    )
    assert result.text == NOTES["rag"]


def test_ignores_unembedded_chunks_and_other_models(conn, embedder) -> None:  # noqa: ANN001
    with conn:
        pending = items_repo.create_item(conn, source_type="note", title="Pending", content="retrieval pending")
        chunks_repo.insert_chunks(conn, pending.id, [Chunk(index=0, text="retrieval pending")])
    other = FakeEmbedder(model_id="fake:other@64")
    add_embedded(conn, other, "Old model", "retrieval from an old model")
    current = add_embedded(conn, embedder, "Current", "retrieval with the current model")

    results = search(conn, embedder, "retrieval")

    assert [r.item_id for r in results] == [current]


def test_empty_inbox_does_not_call_the_embedder(conn, embedder) -> None:  # noqa: ANN001
    assert search(conn, embedder, "anything") == []
    assert embedder.query_calls == []


def test_ties_are_ordered_by_chunk_id(conn, embedder) -> None:  # noqa: ANN001
    first = add_embedded(conn, embedder, "A", "identical text")
    second = add_embedded(conn, embedder, "B", "identical text")

    assert [r.item_id for r in search(conn, embedder, "identical text")] == [first, second]


def test_vectors_with_wrong_dimensions_are_skipped(conn, embedder) -> None:  # noqa: ANN001
    good = add_embedded(conn, embedder, "Good", "vector search")
    with conn:
        bad = items_repo.create_item(conn, source_type="note", title="Bad", content="vector search")
        chunks_repo.insert_chunks(conn, bad.id, [Chunk(index=0, text="vector search")])
        chunk = chunks_repo.list_chunks(conn, bad.id)[0]
        conn.execute(
            "UPDATE chunks SET embedding = ?, embedding_model = ? WHERE id = ?",
            (to_blob(np.ones(3)), embedder.model_id, chunk.id),
        )

    assert [r.item_id for r in search(conn, embedder, "vector search")] == [good]


def test_unconfigured_embedder_raises_setup_error(conn) -> None:  # noqa: ANN001
    with pytest.raises(AINotConfiguredError, match="set EMBEDDING_API_KEY"):
        search(conn, UnconfiguredEmbedder(), "anything")
