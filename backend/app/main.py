"""App factory: wires settings, logging, middleware and routers. No business logic here."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health
from app.config import get_settings
from app.logging_config import setup_logging
from app.middleware import REQUEST_ID_HEADER, RequestContextMiddleware


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level)

    app = FastAPI(title="AI Knowledge Inbox API", version="0.1.0")

    # Added last-to-first: RequestContextMiddleware runs inside CORS.
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[REQUEST_ID_HEADER],
    )

    app.include_router(health.router)
    return app


app = create_app()
