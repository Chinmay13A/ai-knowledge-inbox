"""SQLite connection handling and schema creation."""

import sqlite3
from collections.abc import Iterator
from pathlib import Path

from fastapi import Request

# Additive only: tables/indexes are created if missing, never altered or dropped.
SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL CHECK (source_type IN ('note', 'url')),
    title       TEXT NOT NULL,
    url         TEXT,
    content     TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'ready', 'failed')),
    error       TEXT,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_items_created_at ON items(created_at DESC);

CREATE TABLE IF NOT EXISTS chunks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id     INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    text        TEXT NOT NULL,
    embedding   BLOB,
    embedding_model TEXT,
    UNIQUE (item_id, chunk_index)
);
CREATE INDEX IF NOT EXISTS idx_chunks_item_id ON chunks(item_id);
"""


def connect(db_path: str) -> sqlite3.Connection:
    # FastAPI may open the connection in a worker thread and use it from an async route.
    # Each connection still belongs to exactly one request, so sharing across threads is safe.
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: str) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = connect(db_path)
    try:
        # WAL lets reads proceed while a write is in progress; the setting persists in the file.
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA)
        # Columns added after a table first shipped (databases created by older versions).
        _add_column_if_missing(conn, "chunks", "embedding_model", "TEXT")
    finally:
        conn.close()


def _add_column_if_missing(conn: sqlite3.Connection, table: str, column: str, column_type: str) -> None:
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")
        conn.commit()


def get_db(request: Request) -> Iterator[sqlite3.Connection]:
    """FastAPI dependency: one connection per request, always closed."""
    conn = connect(request.app.state.settings.db_path)
    try:
        yield conn
    finally:
        conn.close()
