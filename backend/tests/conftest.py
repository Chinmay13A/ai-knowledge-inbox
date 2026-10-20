from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def app(tmp_path: Path) -> FastAPI:
    """App wired to a throwaway SQLite file, so tests never touch real data."""
    return create_app(Settings(db_path=str(tmp_path / "test.db")))


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    # Entering the context runs the lifespan, which creates the schema.
    with TestClient(app) as test_client:
        yield test_client


def add_note(client: TestClient, content: str) -> dict:
    response = client.post("/ingest", json={"type": "note", "content": content})
    assert response.status_code == 201, response.text
    return response.json()
