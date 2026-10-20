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
