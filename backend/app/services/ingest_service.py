"""Ingestion pipeline: turns user input into stored items and their chunks."""

import dataclasses
import logging
import sqlite3

from app.errors import DuplicateUrlError
from app.models.chunk import ChunkingConfig
from app.models.item import Item, SourceType
from app.repositories import chunks_repo, items_repo
from app.services.chunker import chunk_text
from app.services.fetcher import PageFetcher

TITLE_MAX_CHARS = 80

logger = logging.getLogger(__name__)


def ingest_note(conn: sqlite3.Connection, content: str, chunking: ChunkingConfig) -> Item:
    return _store(conn, chunking, source_type="note", title=derive_title(content), content=content)


async def ingest_url(conn: sqlite3.Connection, fetcher: PageFetcher, url: str, chunking: ChunkingConfig) -> Item:
    """Fetches the page first; nothing is stored if fetching or extraction fails, or if the URL
    (as submitted, or after redirects) is already saved."""
    _ensure_not_saved(conn, url)  # before fetching: no network call for a known URL
    page = await fetcher.fetch(url)
    if page.url != url:
        _ensure_not_saved(conn, page.url)  # e.g. http -> https, or a short link
    return _store(
        conn,
        chunking,
        source_type="url",
        url=page.url,
        title=page.title or derive_title(page.text),
        content=page.text,
    )


def backfill_chunks(conn: sqlite3.Connection, chunking: ChunkingConfig) -> tuple[int, int]:
    """Chunks items saved before chunking existed. Returns (items processed, chunks created)."""
    item_ids = chunks_repo.item_ids_without_chunks(conn)
    total_chunks = 0
    for item_id in item_ids:
        item = items_repo.get_item(conn, item_id)
        if item is None:
            continue
        with conn:
            total_chunks += _save_chunks(conn, item_id, item.content, chunking)
    return len(item_ids), total_chunks


def _ensure_not_saved(conn: sqlite3.Connection, url: str) -> None:
    existing = items_repo.find_by_url(conn, url)
    if existing:
        logger.info("item.duplicate_url", extra={"existing_item_id": existing.id})
        raise DuplicateUrlError(f'This URL is already saved as "{existing.title}"', item_id=existing.id)


def derive_title(text: str, max_len: int = TITLE_MAX_CHARS) -> str:
    """First non-empty line with whitespace collapsed, truncated with an ellipsis."""
    first_line = next((line for line in text.splitlines() if line.strip()), "")
    title = " ".join(first_line.split())
    if len(title) > max_len:
        title = title[: max_len - 1].rstrip() + "…"
    return title or "Untitled"


def _store(
    conn: sqlite3.Connection,
    chunking: ChunkingConfig,
    *,
    source_type: SourceType,
    title: str,
    content: str,
    url: str | None = None,
) -> Item:
    # The item and its chunks are written in one transaction: both are saved or neither is.
    with conn:
        item = items_repo.create_item(conn, source_type=source_type, title=title, content=content, url=url)
        chunk_count = _save_chunks(conn, item.id, content, chunking)
    item = dataclasses.replace(item, chunk_count=chunk_count)
    logger.info(
        "item.ingested",
        extra={
            "item_id": item.id,
            "source_type": item.source_type,
            "url": item.url,
            "content_chars": len(item.content),
            "chunk_count": chunk_count,
        },
    )
    return item


def _save_chunks(conn: sqlite3.Connection, item_id: int, content: str, chunking: ChunkingConfig) -> int:
    chunks = chunk_text(content, size=chunking.size, overlap=chunking.overlap)
    chunks_repo.insert_chunks(conn, item_id, chunks)
    return len(chunks)
