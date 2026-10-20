"""Data access for the `chunks` table. All chunk SQL lives here; callers own the transaction."""

import sqlite3

from app.models.chunk import Chunk, StoredChunk


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
