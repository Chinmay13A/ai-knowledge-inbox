"""Shared FastAPI dependencies for app-wide services and settings."""

from fastapi import Request

from app.models.chunk import ChunkingConfig
from app.services.fetcher import PageFetcher


def get_fetcher(request: Request) -> PageFetcher:
    return request.app.state.fetcher


def get_chunking_config(request: Request) -> ChunkingConfig:
    return request.app.state.settings.chunking
