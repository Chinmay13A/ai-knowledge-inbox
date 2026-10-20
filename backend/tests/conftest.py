import hashlib
import re
from collections.abc import Iterator
from pathlib import Path

import numpy as np
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


class FakeEmbedder:
    """Deterministic, offline Embedder: a bag-of-words hashed into a small vector.

    Texts sharing words get similar vectors, which is enough to test retrieval logic.
    """

    def __init__(self, dimensions: int = 64, model_id: str = "fake:hash@64") -> None:
        self.dimensions = dimensions
        self.model_id = model_id
        self.error: Exception | None = None
        self.document_calls: list[list[str]] = []
        self.query_calls: list[str] = []

    def check_ready(self) -> None:
        pass

    async def embed_documents(self, texts: list[str]) -> list[np.ndarray]:
        self.document_calls.append(list(texts))
        if self.error:
            raise self.error
        return [self.vector(text) for text in texts]

    async def embed_query(self, text: str) -> np.ndarray:
        self.query_calls.append(text)
        if self.error:
            raise self.error
        return self.vector(text)

    def vector(self, text: str) -> np.ndarray:
        vector = np.zeros(self.dimensions, dtype=np.float32)
        for word in re.findall(r"\w+", text.lower()):
            vector[int(hashlib.md5(word.encode()).hexdigest(), 16) % self.dimensions] += 1.0
        norm = np.linalg.norm(vector)
        return vector / norm if norm else vector


def make_settings(tmp_path: Path, **overrides: object) -> Settings:
    """Settings that ignore backend/.env, so a developer's real keys never leak into tests."""
    return Settings(_env_file=None, db_path=str(tmp_path / "test.db"), **overrides)


@pytest.fixture
def fetcher() -> StubFetcher:
    return StubFetcher()


@pytest.fixture
def embedder() -> FakeEmbedder:
    return FakeEmbedder()


@pytest.fixture
def app(tmp_path: Path, fetcher: StubFetcher, embedder: FakeEmbedder) -> FastAPI:
    """App wired to a throwaway SQLite file and fakes, so tests never touch real data or the network."""
    return create_app(make_settings(tmp_path), fetcher=fetcher, embedder=embedder)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    # Entering the context runs the lifespan, which creates the schema.
    with TestClient(app) as test_client:
        yield test_client


def add_note(client: TestClient, content: str) -> dict:
    response = client.post("/ingest", json={"type": "note", "content": content})
    assert response.status_code == 201, response.text
    return response.json()
