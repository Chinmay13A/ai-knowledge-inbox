"""Operations on saved items that aren't part of ingestion or querying."""

import logging
import sqlite3

from app.errors import ItemNotFoundError
from app.repositories import items_repo

logger = logging.getLogger(__name__)


def delete_item(conn: sqlite3.Connection, item_id: int) -> None:
    """Deletes an item and its chunks. A background embedding still running for it just updates
    zero rows afterwards, so deleting mid-indexing is safe."""
    item = items_repo.get_item(conn, item_id)
    if item is None:
        raise ItemNotFoundError(f"Item {item_id} not found")
    with conn:
        items_repo.delete_item(conn, item_id)
    logger.info("item.deleted", extra={"item_id": item_id, "chunks_deleted": item.chunk_count})
