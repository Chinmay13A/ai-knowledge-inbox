import sqlite3
import threading
import time
from pathlib import Path

from app.db import connect, init_db

# The chunks table as created by an earlier version, before embedding_model existed.
OLDER_SCHEMA = """
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
    db_path = str(tmp_path / "older-version.db")
    conn = sqlite3.connect(db_path)
    conn.executescript(OLDER_SCHEMA)
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


def test_concurrent_writer_waits_instead_of_failing(tmp_path: Path) -> None:
    db_path = str(tmp_path / "busy.db")
    init_db(db_path)
    holder = connect(db_path)
    holder.execute("BEGIN IMMEDIATE")  # take the write lock
    holder.execute("INSERT INTO items (source_type, title, content, created_at) VALUES ('note', 'a', 'a', 'now')")
    threading.Timer(0.5, holder.commit).start()  # release it shortly

    writer = connect(db_path)
    start = time.monotonic()
    with writer:
        writer.execute("INSERT INTO items (source_type, title, content, created_at) VALUES ('note', 'b', 'b', 'now')")
    waited = time.monotonic() - start

    assert 0.3 < waited < 5  # waited for the lock rather than raising "database is locked"
    assert writer.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 2
    writer.close()
    holder.close()
