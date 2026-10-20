import sqlite3

from fastapi import APIRouter, BackgroundTasks, Depends

from app.ai.embeddings.base import Embedder
from app.api.deps import get_chunking_config, get_db_path, get_embedder, get_fetcher
from app.db import get_db
from app.models.chunk import ChunkingConfig
from app.models.schemas import IngestRequest, ItemOut, NoteIngestRequest
from app.services import embedding_service, ingest_service
from app.services.fetcher import PageFetcher

router = APIRouter(tags=["ingest"])


@router.post(
    "/ingest",
    response_model=ItemOut,
    status_code=201,
    summary="Save a note or URL",
    description="Stores the item and its chunks, then embeds them in the background. "
    "The response has status 'pending'; poll GET /items until it is 'ready' (or 'failed').",
)
async def ingest(
    payload: IngestRequest,
    background_tasks: BackgroundTasks,
    conn: sqlite3.Connection = Depends(get_db),
    fetcher: PageFetcher = Depends(get_fetcher),
    chunking: ChunkingConfig = Depends(get_chunking_config),
    embedder: Embedder = Depends(get_embedder),
    db_path: str = Depends(get_db_path),
) -> ItemOut:
    if isinstance(payload, NoteIngestRequest):
        item = ingest_service.ingest_note(conn, payload.content, chunking)
    else:
        item = await ingest_service.ingest_url(conn, fetcher, str(payload.url), chunking)
    # Runs after the response is sent, with its own DB connection.
    background_tasks.add_task(embedding_service.embed_item, db_path, embedder, item.id)
    return ItemOut.from_item(item)
