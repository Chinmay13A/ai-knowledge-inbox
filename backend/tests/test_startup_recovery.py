import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.db import connect, init_db
from app.main import create_app
from app.models.chunk import Chunk
from app.repositories import chunks_repo, items_repo
from tests.conftest import FakeChatModel, FakeEmbedder, StubFetcher, make_settings


def seed(db_path: str) -> dict[str, int]:
    """An item left 'pending' by a crashed run, and one that already failed."""
    init_db(db_path)
    conn = connect(db_path)
    ids = {}
    with conn:
        for status in ("pending", "failed"):
            item = items_repo.create_item(conn, source_type="note", title=status, content=f"{status} note text")
            chunks_repo.insert_chunks(conn, item.id, [Chunk(index=0, text=f"{status} note text")])
            items_repo.set_status(conn, item.id, status, error="old error" if status == "failed" else None)
            ids[status] = item.id
    conn.close()
    return ids


def statuses(client: TestClient) -> dict[str, str]:
    return {item["title"]: item["status"] for item in client.get("/items").json()["items"]}


def start_app(tmp_path: Path, embedder: FakeEmbedder, **settings: object) -> TestClient:
    app = create_app(
        make_settings(tmp_path, **settings), fetcher=StubFetcher(), embedder=embedder, chat_model=FakeChatModel()
    )
    return TestClient(app)


def test_pending_items_are_embedded_on_startup(tmp_path: Path) -> None:
    seed(str(tmp_path / "test.db"))
    embedder = FakeEmbedder()

    with start_app(tmp_path, embedder) as client:
        deadline = time.monotonic() + 5
        while statuses(client)["pending"] != "ready" and time.monotonic() < deadline:
            time.sleep(0.05)
        result = statuses(client)

    assert result == {"pending": "ready", "failed": "failed"}  # failed items are left for the reindex script
    assert embedder.document_calls == [["pending note text"]]


def test_recovery_can_be_disabled(tmp_path: Path) -> None:
    seed(str(tmp_path / "test.db"))
    embedder = FakeEmbedder()

    with start_app(tmp_path, embedder, recover_pending_on_startup=False) as client:
        time.sleep(0.2)
        result = statuses(client)

    assert result["pending"] == "pending"
    assert embedder.document_calls == []
