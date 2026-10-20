import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import connect
from app.services.embedding_service import embed_item
from tests.conftest import FakeEmbedder, add_note


def test_empty_inbox(client: TestClient) -> None:
    response = client.get("/items")

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "limit": 50, "offset": 0}


def test_items_are_listed_newest_first(client: TestClient) -> None:
    first = add_note(client, "first")
    second = add_note(client, "second")

    ids = [item["id"] for item in client.get("/items").json()["items"]]

    assert ids == [second["id"], first["id"]]


def test_pagination_keeps_full_total(client: TestClient) -> None:
    notes = [add_note(client, f"note {i}") for i in range(5)]

    body = client.get("/items", params={"limit": 2, "offset": 1}).json()

    assert body["total"] == 5
    assert [item["id"] for item in body["items"]] == [notes[3]["id"], notes[2]["id"]]


def test_preview_is_truncated(client: TestClient) -> None:
    add_note(client, "x" * 500)

    item = client.get("/items").json()["items"][0]

    assert len(item["preview"]) == 200


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 500}, {"offset": -1}, {"limit": "abc"}])
def test_invalid_query_params_are_rejected(client: TestClient, params: dict) -> None:
    response = client.get("/items", params=params)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


class TestItemChunks:
    def test_returns_chunks_of_item(self, client: TestClient) -> None:
        item = add_note(client, "Line one.\nLine two.")

        body = client.get(f"/items/{item['id']}/chunks").json()

        assert body == {"item_id": item["id"], "chunks": [{"index": 0, "text": "Line one.\nLine two.", "chars": 19}]}

    def test_unknown_item_is_404(self, client: TestClient) -> None:
        response = client.get("/items/999/chunks")

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "item_not_found"
        assert response.json()["error"]["message"] == "Item 999 not found"

    def test_non_numeric_id_is_422(self, client: TestClient) -> None:
        response = client.get("/items/abc/chunks")

        assert response.status_code == 422


class TestDeleteItem:
    def test_delete_removes_item_and_chunks(self, client: TestClient) -> None:
        keep = add_note(client, "keep me")
        gone = add_note(client, "delete me")

        response = client.delete(f"/items/{gone['id']}")

        assert response.status_code == 204
        assert response.content == b""
        assert [item["id"] for item in client.get("/items").json()["items"]] == [keep["id"]]
        assert client.get(f"/items/{gone['id']}/chunks").status_code == 404

    def test_deleting_twice_is_404(self, client: TestClient) -> None:
        item = add_note(client, "once")
        client.delete(f"/items/{item['id']}")

        response = client.delete(f"/items/{item['id']}")

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "item_not_found"

    def test_non_numeric_id_is_422(self, client: TestClient) -> None:
        assert client.delete("/items/abc").status_code == 422

    def test_delete_during_embedding_does_not_resurrect_rows(self, client: TestClient, app: FastAPI) -> None:
        item = add_note(client, "racing note")
        client.delete(f"/items/{item['id']}")

        # The background task for this item finishing late must be harmless.
        outcome = asyncio.run(embed_item(app.state.settings.db_path, FakeEmbedder(model_id="fake:late@64"), item["id"]))

        assert outcome.chunks_embedded == 0
        conn = connect(app.state.settings.db_path)
        assert conn.execute("SELECT COUNT(*) FROM chunks WHERE item_id = ?", (item["id"],)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM items WHERE id = ?", (item["id"],)).fetchone()[0] == 0
        conn.close()
