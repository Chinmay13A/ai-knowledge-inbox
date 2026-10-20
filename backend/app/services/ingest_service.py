"""Ingestion pipeline: turns user input into stored items."""

import logging
import sqlite3

from app.models.item import Item
from app.repositories import items_repo
from app.services.fetcher import PageFetcher

TITLE_MAX_CHARS = 80

logger = logging.getLogger(__name__)


def ingest_note(conn: sqlite3.Connection, content: str) -> Item:
    item = items_repo.create_item(conn, source_type="note", title=derive_title(content), content=content)
    _log_ingested(item)
    return item


async def ingest_url(conn: sqlite3.Connection, fetcher: PageFetcher, url: str) -> Item:
    """Fetches the page first; nothing is stored if fetching or extraction fails."""
    page = await fetcher.fetch(url)
    item = items_repo.create_item(
        conn,
        source_type="url",
        url=page.url,
        title=page.title or derive_title(page.text),
        content=page.text,
    )
    _log_ingested(item)
    return item


def _log_ingested(item: Item) -> None:
    logger.info(
        "item.ingested",
        extra={
            "item_id": item.id,
            "source_type": item.source_type,
            "url": item.url,
            "content_chars": len(item.content),
        },
    )


def derive_title(text: str, max_len: int = TITLE_MAX_CHARS) -> str:
    """First non-empty line with whitespace collapsed, truncated with an ellipsis."""
    first_line = next((line for line in text.splitlines() if line.strip()), "")
    title = " ".join(first_line.split())
    if len(title) > max_len:
        title = title[: max_len - 1].rstrip() + "…"
    return title or "Untitled"
