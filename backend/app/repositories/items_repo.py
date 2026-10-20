"""Data access for the `items` table. All item SQL lives here; callers own the transaction."""

import sqlite3
from datetime import datetime, timezone

from app.models.item import Item, SourceType

_SELECT_ITEMS = """
    SELECT items.*,
           (SELECT COUNT(*) FROM chunks WHERE chunks.item_id = items.id) AS chunk_count
    FROM items
"""


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
    item = get_item(conn, cursor.lastrowid)
    assert item is not None  # just inserted in this transaction
    return item


def get_item(conn: sqlite3.Connection, item_id: int) -> Item | None:
    row = conn.execute(f"{_SELECT_ITEMS} WHERE items.id = ?", (item_id,)).fetchone()
    return Item.from_row(row) if row else None


def list_items(conn: sqlite3.Connection, *, limit: int, offset: int) -> tuple[list[Item], int]:
    rows = conn.execute(
        f"{_SELECT_ITEMS} ORDER BY items.created_at DESC, items.id DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    total = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    return [Item.from_row(row) for row in rows], total
