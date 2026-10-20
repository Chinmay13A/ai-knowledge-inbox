"""Data access for the `chunks` table. All chunk SQL lives here; callers own the transaction."""

import sqlite3

import numpy as np

from app.models.chunk import Chunk, StoredChunk
from app.services.vectors import to_blob


def insert_chunks(conn: sqlite3.Connection, item_id: int, chunks: list[Chunk]) -> None:
    conn.executemany(
        "INSERT INTO chunks (item_id, chunk_index, text) VALUES (?, ?, ?)",
        [(item_id, chunk.index, chunk.text) for chunk in chunks],
    )


def list_chunks(conn: sqlite3.Connection, item_id: int) -> list[StoredChunk]:
    rows = conn.execute(
        "SELECT id, item_id, chunk_index, text FROM chunks WHERE item_id = ? ORDER BY chunk_index",
        (item_id,),
    ).fetchall()
    return [StoredChunk.from_row(row) for row in rows]


def item_ids_without_chunks(conn: sqlite3.Connection) -> list[int]:
    rows = conn.execute(
        "SELECT id FROM items WHERE NOT EXISTS (SELECT 1 FROM chunks WHERE chunks.item_id = items.id) ORDER BY id"
    ).fetchall()
    return [row["id"] for row in rows]


def chunks_missing_embeddings(conn: sqlite3.Connection, item_id: int, model_id: str) -> list[StoredChunk]:
    """Chunks with no vector yet, or a vector from a different model (needs re-embedding)."""
    rows = conn.execute(
        """
        SELECT id, item_id, chunk_index, text FROM chunks
        WHERE item_id = ? AND (embedding IS NULL OR embedding_model IS NOT ?)
        ORDER BY chunk_index
        """,
        (item_id, model_id),
    ).fetchall()
    return [StoredChunk.from_row(row) for row in rows]


def set_embeddings(conn: sqlite3.Connection, vectors: list[tuple[int, np.ndarray]], model_id: str) -> None:
    conn.executemany(
        "UPDATE chunks SET embedding = ?, embedding_model = ? WHERE id = ?",
        [(to_blob(vector), model_id, chunk_id) for chunk_id, vector in vectors],
    )


def embedded_chunks(conn: sqlite3.Connection, model_id: str) -> list[sqlite3.Row]:
    """Every chunk with a vector from `model_id`, joined with its item's metadata (for retrieval)."""
    return conn.execute(
        """
        SELECT chunks.id AS chunk_id, chunks.item_id, chunks.chunk_index, chunks.text, chunks.embedding,
               items.title AS item_title, items.url AS item_url, items.source_type
        FROM chunks JOIN items ON items.id = chunks.item_id
        WHERE chunks.embedding IS NOT NULL AND chunks.embedding_model = ?
        ORDER BY chunks.id
        """,
        (model_id,),
    ).fetchall()
