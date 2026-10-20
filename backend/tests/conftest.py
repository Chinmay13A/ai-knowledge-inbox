from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services.fetcher import FetchedPage


class StubFetcher:
    """Stands in for PageFetcher in API tests: returns a fixed page or raises a fixed error."""

    def __init__(self, result: FetchedPage | Exception | None = None) -> None:
        self.result = result or FetchedPage(url="https://example.com/article", title="Example", text="Body")
        self.requested: list[str] = []

    async def fetch(self, url: str) -> FetchedPage:
        self.requested.append(url)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.fixture
def fetcher() -> StubFetcher:
    return StubFetcher()


@pytest.fixture
def app(tmp_path: Path, fetcher: StubFetcher) -> FastAPI:
    """App wired to a throwaway SQLite file and a stub fetcher, so tests never touch real data or the network."""
    return create_app(Settings(db_path=str(tmp_path / "test.db")), fetcher=fetcher)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    # Entering the context runs the lifespan, which creates the schema.
    with TestClient(app) as test_client:
        yield test_client


def add_note(client: TestClient, content: str) -> dict:
    response = client.post("/ingest", json={"type": "note", "content": content})
    assert response.status_code == 201, response.text
    return response.json()
