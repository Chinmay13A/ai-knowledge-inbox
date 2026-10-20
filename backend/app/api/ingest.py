import sqlite3

from fastapi import APIRouter, Depends

from app.api.deps import get_chunking_config, get_fetcher
from app.db import get_db
from app.models.chunk import ChunkingConfig
from app.models.schemas import IngestRequest, ItemOut, NoteIngestRequest
from app.services import ingest_service
from app.services.fetcher import PageFetcher

router = APIRouter(tags=["ingest"])


@router.post("/ingest", response_model=ItemOut, status_code=201, summary="Save a note or URL")
async def ingest(
    payload: IngestRequest,
    conn: sqlite3.Connection = Depends(get_db),
    fetcher: PageFetcher = Depends(get_fetcher),
    chunking: ChunkingConfig = Depends(get_chunking_config),
) -> ItemOut:
    if isinstance(payload, NoteIngestRequest):
        item = ingest_service.ingest_note(conn, payload.content, chunking)
    else:
        item = await ingest_service.ingest_url(conn, fetcher, str(payload.url), chunking)
    return ItemOut.from_item(item)
