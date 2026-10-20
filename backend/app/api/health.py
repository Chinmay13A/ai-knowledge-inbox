import logging
import sqlite3
from typing import Literal

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from app.db import connect
from app.errors import AINotConfiguredError

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)

Readiness = Literal["ready", "not_configured"]


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["ok", "error"]
    embeddings: Readiness
    llm: Readiness


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Readiness: database and AI provider configuration",
    description="200 when the database works (missing AI keys are reported, not fatal); 503 if the database is down.",
)
def health(request: Request, response: Response) -> HealthResponse:
    state = request.app.state
    database = _check_database(state.settings.db_path)
    if database == "error":
        response.status_code = 503
    return HealthResponse(
        status="ok" if database == "ok" else "degraded",
        database=database,
        embeddings=_readiness(state.embedder),
        llm=_readiness(state.chat_model),
    )


def _check_database(db_path: str) -> Literal["ok", "error"]:
    try:
        conn = connect(db_path)
        try:
            conn.execute("SELECT 1").fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("health.database_error")
        return "error"
    return "ok"


def _readiness(provider: object) -> Readiness:
    try:
        provider.check_ready()  # type: ignore[attr-defined]  # Embedder and ChatModel both define it
    except AINotConfiguredError:
        return "not_configured"
    return "ready"
