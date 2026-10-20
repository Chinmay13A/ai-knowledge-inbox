"""Shared FastAPI dependencies for app-wide services."""

from fastapi import Request

from app.services.fetcher import PageFetcher


def get_fetcher(request: Request) -> PageFetcher:
    return request.app.state.fetcher
