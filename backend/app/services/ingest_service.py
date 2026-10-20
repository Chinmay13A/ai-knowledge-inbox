"""Ingestion pipeline: turns user input into stored items."""

import logging
import sqlite3

from app.models.item import Item
from app.repositories import items_repo

TITLE_MAX_CHARS = 80

logger = logging.getLogger(__name__)


def ingest_note(conn: sqlite3.Connection, content: str) -> Item:
    item = items_repo.create_item(conn, source_type="note", title=derive_title(content), content=content)
    logger.info(
        "item.ingested",
        extra={"item_id": item.id, "source_type": item.source_type, "content_chars": len(content)},
    )
    return item


def derive_title(text: str, max_len: int = TITLE_MAX_CHARS) -> str:
    """First non-empty line with whitespace collapsed, truncated with an ellipsis."""
    first_line = next((line for line in text.splitlines() if line.strip()), "")
    title = " ".join(first_line.split())
    if len(title) > max_len:
        title = title[: max_len - 1].rstrip() + "…"
    return title or "Untitled"
