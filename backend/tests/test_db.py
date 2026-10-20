import sqlite3
from pathlib import Path

from app.db import init_db

# The chunks table as created by Step 3, before embedding_model existed.
STEP3_SCHEMA = """
CREATE TABLE items (
    id INTEGER PRIMARY KEY AUTOINCREMENT, source_type TEXT NOT NULL, title TEXT NOT NULL, url TEXT,
    content TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', error TEXT, created_at TEXT NOT NULL
);
CREATE TABLE chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT, item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL, text TEXT NOT NULL, embedding BLOB, UNIQUE (item_id, chunk_index)
);
INSERT INTO items (source_type, title, content, created_at) VALUES ('note', 'Old', 'Old note', '2026-01-01');
INSERT INTO chunks (item_id, chunk_index, text) VALUES (1, 0, 'Old note');
"""


def columns(db_path: str, table: str) -> set[str]:
    conn = sqlite3.connect(db_path)
    try:
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    finally:
        conn.close()


def test_init_db_upgrades_older_database_without_losing_data(tmp_path: Path) -> None:
    db_path = str(tmp_path / "step3.db")
    conn = sqlite3.connect(db_path)
    conn.executescript(STEP3_SCHEMA)
    conn.close()

    init_db(db_path)
    init_db(db_path)  # idempotent

    assert "embedding_model" in columns(db_path, "chunks")
    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT text FROM chunks").fetchone()[0] == "Old note"
    conn.close()


def test_fresh_database_has_full_schema(tmp_path: Path) -> None:
    db_path = str(tmp_path / "fresh.db")

    init_db(db_path)

    assert {"embedding", "embedding_model"} <= columns(db_path, "chunks")
