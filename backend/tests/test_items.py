import pytest
from fastapi.testclient import TestClient

from tests.conftest import add_note


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
