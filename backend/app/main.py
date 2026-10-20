"""App factory: wires settings, logging, middleware and routers. No business logic here."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.ai.embeddings.base import Embedder
from app.ai.embeddings.factory import build_embedder
from app.ai.llm.base import ChatModel
from app.ai.llm.factory import build_chat_model
from app.api import health, ingest, items, query, search
from app.config import Settings, get_settings
from app.db import init_db
from app.errors import register_exception_handlers
from app.logging_config import setup_logging
from app.middleware import REQUEST_ID_HEADER, RequestContextMiddleware
from app.services.fetcher import PageFetcher

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    db_path = app.state.settings.db_path
    init_db(db_path)
    logger.info("db.initialized", extra={"db_path": db_path})
    yield


def create_app(
    settings: Settings | None = None,
    fetcher: PageFetcher | None = None,
    embedder: Embedder | None = None,
    chat_model: ChatModel | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    setup_logging(settings.log_level)

    app = FastAPI(title="AI Knowledge Inbox API", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.fetcher = fetcher or PageFetcher(
        timeout_s=settings.fetch_timeout_s,
        max_bytes=settings.fetch_max_bytes,
        respect_robots_txt=settings.respect_robots_txt,
    )
    app.state.embedder = embedder or build_embedder(settings)
    app.state.chat_model = chat_model or build_chat_model(settings)

    # Added last-to-first: RequestContextMiddleware runs inside CORS.
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[REQUEST_ID_HEADER],
    )

    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(ingest.router)
    app.include_router(items.router)
    app.include_router(search.router)
    app.include_router(query.router)
    return app


app = create_app()
