"""App factory: wires settings, logging, middleware and routers. No business logic here."""

import asyncio
import contextlib
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
from app.middleware import REQUEST_ID_HEADER, BodySizeLimitMiddleware, RequestContextMiddleware
from app.services import embedding_service
from app.services.fetcher import PageFetcher

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    init_db(settings.db_path)
    logger.info("db.initialized", extra={"db_path": settings.db_path})

    recovery = None
    if settings.recover_pending_on_startup:
        # Runs in the background so startup isn't blocked by provider calls.
        recovery = asyncio.create_task(_recover_pending(settings.db_path, app.state.embedder))
    app.state.recovery_task = recovery
    yield
    if recovery and not recovery.done():
        recovery.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await recovery


async def _recover_pending(db_path: str, embedder: Embedder) -> None:
    """Embeds items left "pending" by a previous run (in-process background tasks die with the server).
    Failed items are not retried here, so restarts don't burn provider quota; the reindex script does that."""
    try:
        items, chunks, failed = await embedding_service.embed_pending(db_path, embedder, only_statuses=("pending",))
    except Exception:
        logger.exception("startup.recovery_failed")
        return
    if items:
        logger.info("startup.recovery", extra={"items": items, "chunks": chunks, "failed": failed})


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

    # Added last-to-first: CORS -> RequestContext (request id, logging) -> body size limit -> routes.
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_request_bytes)
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
