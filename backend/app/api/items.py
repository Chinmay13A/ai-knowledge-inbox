import sqlite3

from fastapi import APIRouter, Depends, Query

from app.db import get_db
from app.errors import ItemNotFoundError
from app.models.schemas import ChunkOut, ItemChunksResponse, ItemListResponse, ItemOut
from app.repositories import chunks_repo, items_repo

router = APIRouter(tags=["items"])


@router.get("/items", response_model=ItemListResponse, summary="List saved items, newest first")
def list_items(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    conn: sqlite3.Connection = Depends(get_db),
) -> ItemListResponse:
    items, total = items_repo.list_items(conn, limit=limit, offset=offset)
    return ItemListResponse(
        items=[ItemOut.from_item(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/items/{item_id}/chunks",
    response_model=ItemChunksResponse,
    summary="Inspect how an item was chunked (debugging aid)",
)
def list_item_chunks(item_id: int, conn: sqlite3.Connection = Depends(get_db)) -> ItemChunksResponse:
    if items_repo.get_item(conn, item_id) is None:
        raise ItemNotFoundError(f"Item {item_id} not found")
    chunks = chunks_repo.list_chunks(conn, item_id)
    return ItemChunksResponse(
        item_id=item_id,
        chunks=[ChunkOut(index=c.chunk_index, text=c.text, chars=len(c.text)) for c in chunks],
    )
