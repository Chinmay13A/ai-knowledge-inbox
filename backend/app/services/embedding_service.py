"""Embedding pipeline: turns an item's chunks into stored vectors and tracks item status.

Runs outside the request (as a background task or from the reindex script), so it opens its
own database connection and never raises: failures are recorded on the item instead.
"""

import logging
import sqlite3
import time
from dataclasses import dataclass

from app.ai.embeddings.base import Embedder
from app.db import connect
from app.errors import AppError
from app.models.item import ItemStatus
from app.repositories import chunks_repo, items_repo

GENERIC_FAILURE = "Embedding failed due to an unexpected error"

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmbeddingOutcome:
    ok: bool
    chunks_embedded: int


async def embed_item(db_path: str, embedder: Embedder, item_id: int) -> EmbeddingOutcome:
    start = time.perf_counter()
    conn = connect(db_path)
    try:
        # Only chunks without a vector from the current model: retries and re-runs are cheap.
        chunks = chunks_repo.chunks_missing_embeddings(conn, item_id, embedder.model_id)
        try:
            vectors = await embedder.embed_documents([chunk.text for chunk in chunks]) if chunks else []
        except AppError as exc:
            return _mark_failed(conn, item_id, exc.message)
        except Exception:
            logger.exception("embedding.failed", extra={"item_id": item_id, "error": GENERIC_FAILURE})
            return _mark_failed(conn, item_id, GENERIC_FAILURE, log=False)

        with conn:  # vectors and the status change land together
            chunks_repo.set_embeddings(conn, list(zip((c.id for c in chunks), vectors, strict=True)), embedder.model_id)
            items_repo.set_status(conn, item_id, "ready")
        logger.info(
            "embedding.completed",
            extra={
                "item_id": item_id,
                "chunks": len(chunks),
                "model_id": embedder.model_id,
                "duration_ms": round((time.perf_counter() - start) * 1000, 2),
            },
        )
        return EmbeddingOutcome(ok=True, chunks_embedded=len(chunks))
    finally:
        conn.close()


async def embed_pending(
    db_path: str, embedder: Embedder, *, only_statuses: tuple[ItemStatus, ...] | None = None
) -> tuple[int, int, int]:
    """Backfill: embeds items that aren't ready for the current model, one at a time
    (gentle on provider rate limits). `only_statuses` narrows it, e.g. to ("pending",) on startup.
    Returns (items processed, chunks embedded, items failed)."""
    conn = connect(db_path)
    try:
        if only_statuses:
            item_ids = items_repo.item_ids_with_status(conn, only_statuses)
        else:
            item_ids = items_repo.item_ids_needing_embedding(conn, embedder.model_id)
    finally:
        conn.close()

    chunks = failed = 0
    for item_id in item_ids:
        outcome = await embed_item(db_path, embedder, item_id)
        chunks += outcome.chunks_embedded
        failed += 0 if outcome.ok else 1
    return len(item_ids), chunks, failed


def _mark_failed(conn: sqlite3.Connection, item_id: int, error: str, *, log: bool = True) -> EmbeddingOutcome:
    with conn:
        items_repo.set_status(conn, item_id, "failed", error=error)
    if log:
        logger.warning("embedding.failed", extra={"item_id": item_id, "error": error})
    return EmbeddingOutcome(ok=False, chunks_embedded=0)
