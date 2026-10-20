import sqlite3

from fastapi import APIRouter, Depends, Query

from app.db import get_db
from app.models.schemas import ItemListResponse, ItemOut
from app.repositories import items_repo

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
