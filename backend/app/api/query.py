import sqlite3

from fastapi import APIRouter, Depends

from app.ai.embeddings.base import Embedder
from app.ai.llm.base import ChatModel
from app.api.deps import get_app_settings, get_chat_model, get_embedder
from app.config import Settings
from app.db import get_db
from app.models.schemas import QueryRequest, QueryResponse
from app.services import query_service

router = APIRouter(tags=["query"])


@router.post(
    "/query",
    response_model=QueryResponse,
    summary="Ask a question about your saved content",
    description="Retrieves the most relevant chunks and asks the LLM to answer from them only. "
    "Each `[n]` in the answer refers to `sources[].id`.",
)
async def query(
    payload: QueryRequest,
    conn: sqlite3.Connection = Depends(get_db),
    embedder: Embedder = Depends(get_embedder),
    chat_model: ChatModel = Depends(get_chat_model),
    settings: Settings = Depends(get_app_settings),
) -> QueryResponse:
    answer = await query_service.answer_question(
        conn,
        embedder,
        chat_model,
        payload.question,
        top_k=payload.top_k or settings.retrieval_top_k,
        min_score=settings.retrieval_min_score,
    )
    return QueryResponse.from_answer(payload.question, answer)
