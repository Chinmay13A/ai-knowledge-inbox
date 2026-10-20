"""Data access for the `items` table. All item SQL lives here; callers own the transaction."""

import sqlite3
from datetime import datetime, timezone

from app.models.item import Item, ItemStatus, SourceType

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


def set_status(conn: sqlite3.Connection, item_id: int, status: ItemStatus, error: str | None = None) -> None:
    conn.execute("UPDATE items SET status = ?, error = ? WHERE id = ?", (status, error, item_id))


def item_ids_needing_embedding(conn: sqlite3.Connection, model_id: str) -> list[int]:
    """Items not yet ready, or with any chunk lacking a vector from the current model."""
    rows = conn.execute(
        """
        SELECT id FROM items
        WHERE status != 'ready'
           OR EXISTS (
               SELECT 1 FROM chunks
               WHERE chunks.item_id = items.id AND (embedding IS NULL OR embedding_model IS NOT ?)
           )
        ORDER BY id
        """,
        (model_id,),
    ).fetchall()
    return [row["id"] for row in rows]


def item_ids_with_status(conn: sqlite3.Connection, statuses: tuple[ItemStatus, ...]) -> list[int]:
    placeholders = ",".join("?" for _ in statuses)
    rows = conn.execute(f"SELECT id FROM items WHERE status IN ({placeholders}) ORDER BY id", statuses).fetchall()
    return [row["id"] for row in rows]


def find_by_url(conn: sqlite3.Connection, url: str) -> Item | None:
    row = conn.execute(f"{_SELECT_ITEMS} WHERE items.url = ? ORDER BY items.id LIMIT 1", (url,)).fetchone()
    return Item.from_row(row) if row else None


def delete_item(conn: sqlite3.Connection, item_id: int) -> bool:
    """Deletes the item; its chunks go with it (ON DELETE CASCADE). Returns False if it didn't exist."""
    return conn.execute("DELETE FROM items WHERE id = ?", (item_id,)).rowcount > 0
