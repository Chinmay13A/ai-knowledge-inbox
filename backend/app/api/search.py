import sqlite3

from fastapi import APIRouter, Depends

from app.ai.embeddings.base import Embedder
from app.api.deps import get_app_settings, get_embedder
from app.config import Settings
from app.db import get_db
from app.models.schemas import SearchRequest, SearchResponse, SearchResult
from app.services import retriever

router = APIRouter(tags=["search"])


@router.post(
    "/search",
    response_model=SearchResponse,
    summary="Find the most relevant chunks for a query (debugging aid)",
    description="Retrieval only, no LLM: shows which chunks POST /query would use as context, with scores.",
)
async def search(
    payload: SearchRequest,
    conn: sqlite3.Connection = Depends(get_db),
    embedder: Embedder = Depends(get_embedder),
    settings: Settings = Depends(get_app_settings),
) -> SearchResponse:
    chunks = await retriever.retrieve(
        conn,
        embedder,
        payload.query,
        top_k=payload.top_k or settings.retrieval_top_k,
        min_score=settings.retrieval_min_score,
    )
    return SearchResponse(query=payload.query, results=[SearchResult.from_chunk(chunk) for chunk in chunks])
