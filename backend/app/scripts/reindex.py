"""Backfill processing for items saved before a pipeline stage existed, or that failed.

- chunks items that have none
- embeds items that are pending/failed, or whose vectors come from a different model
  (e.g. after switching EMBEDDING_PROVIDER / EMBEDDING_MODEL)

Usage (from backend/):  python -m app.scripts.reindex
"""

import asyncio

from app.ai.embeddings.factory import build_embedder
from app.config import get_settings
from app.db import connect, init_db
from app.logging_config import setup_logging
from app.services import embedding_service, ingest_service


def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    init_db(settings.db_path)

    conn = connect(settings.db_path)
    try:
        items, chunks = ingest_service.backfill_chunks(conn, settings.chunking)
    finally:
        conn.close()
    print(f"Chunked {items} items ({chunks} chunks)")

    embedder = build_embedder(settings)
    items, chunks, failed = asyncio.run(embedding_service.embed_pending(settings.db_path, embedder))
    print(f"Embedded {items - failed} items ({chunks} chunks), {failed} failed  [model: {embedder.model_id}]")
    if failed:
        print("Failed items show the reason in GET /items (field 'error'). Fix the cause and run this again.")


if __name__ == "__main__":
    main()
