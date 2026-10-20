import sqlite3

from fastapi import APIRouter, Depends

from app.db import get_db
from app.errors import NotImplementedFeatureError
from app.models.schemas import IngestRequest, ItemOut, NoteIngestRequest
from app.services import ingest_service

router = APIRouter(tags=["ingest"])


@router.post("/ingest", response_model=ItemOut, status_code=201, summary="Save a note or URL")
def ingest(payload: IngestRequest, conn: sqlite3.Connection = Depends(get_db)) -> ItemOut:
    if isinstance(payload, NoteIngestRequest):
        item = ingest_service.ingest_note(conn, payload.content)
        return ItemOut.from_item(item)
    raise NotImplementedFeatureError("URL ingestion is not supported yet")
