"""Shared FastAPI dependencies for app-wide services and settings."""

from fastapi import Request

from app.ai.embeddings.base import Embedder
from app.ai.llm.base import ChatModel
from app.config import Settings
from app.models.chunk import ChunkingConfig
from app.services.fetcher import PageFetcher


def get_fetcher(request: Request) -> PageFetcher:
    return request.app.state.fetcher


def get_chunking_config(request: Request) -> ChunkingConfig:
    return request.app.state.settings.chunking


def get_embedder(request: Request) -> Embedder:
    return request.app.state.embedder


def get_db_path(request: Request) -> str:
    return request.app.state.settings.db_path


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_chat_model(request: Request) -> ChatModel:
    return request.app.state.chat_model
