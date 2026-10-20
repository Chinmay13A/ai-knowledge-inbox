"""Data access for the `items` table. All item SQL lives here."""

import sqlite3
from datetime import datetime, timezone

from app.models.item import Item, SourceType


def create_item(
    conn: sqlite3.Connection,
    *,
    source_type: SourceType,
    title: str,
    content: str,
    url: str | None = None,
) -> Item:
    created_at = datetime.now(timezone.utc).isoformat()
    cursor = conn.execute(
        "INSERT INTO items (source_type, title, url, content, created_at) VALUES (?, ?, ?, ?, ?)",
        (source_type, title, url, content, created_at),
    )
    conn.commit()
    return get_item(conn, cursor.lastrowid)


def get_item(conn: sqlite3.Connection, item_id: int) -> Item:
    row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    return Item.from_row(row)


def list_items(conn: sqlite3.Connection, *, limit: int, offset: int) -> tuple[list[Item], int]:
    rows = conn.execute(
        "SELECT * FROM items ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    total = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    return [Item.from_row(row) for row in rows], total
