"""Backfill processing for items saved before a pipeline stage existed.

Usage (from backend/):  python -m app.scripts.reindex
"""

from app.config import get_settings
from app.db import connect, init_db
from app.services import ingest_service


def main() -> None:
    settings = get_settings()
    init_db(settings.db_path)
    conn = connect(settings.db_path)
    try:
        items, chunks = ingest_service.backfill_chunks(conn, settings.chunking)
    finally:
        conn.close()
    print(f"Chunked {items} items ({chunks} chunks)")


if __name__ == "__main__":
    main()
