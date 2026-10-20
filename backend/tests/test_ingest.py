import pytest
from fastapi.testclient import TestClient

from app.models.schemas import MAX_NOTE_CHARS
from app.services.ingest_service import derive_title
from tests.conftest import add_note


def test_ingest_note_returns_created_item(client: TestClient) -> None:
    item = add_note(client, "  Meeting notes\nShip v1 by Friday.  ")

    assert isinstance(item["id"], int)
    assert item["source_type"] == "note"
    assert item["status"] == "pending"
    assert item["title"] == "Meeting notes"
    assert item["url"] is None
    assert item["preview"] == "Meeting notes\nShip v1 by Friday."
    assert item["created_at"]


@pytest.mark.parametrize(
    ("payload", "expected_message"),
    [
        ({"type": "note", "content": "   \n "}, "content: must not be blank"),
        ({"type": "note", "content": "x" * (MAX_NOTE_CHARS + 1)}, "content: must be at most"),
        ({"type": "note"}, "content: Field required"),
        ({"content": "hello"}, "Unable to extract tag"),
        ({"type": "pdf", "content": "hello"}, "does not match any of the expected tags"),
    ],
)
def test_invalid_payloads_are_rejected(client: TestClient, payload: dict, expected_message: str) -> None:
    response = client.post("/ingest", json=payload)

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert expected_message in error["message"]
    assert error["details"]


def test_malformed_json_is_bad_request(client: TestClient) -> None:
    response = client.post("/ingest", content="{oops", headers={"Content-Type": "application/json"})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_json"


def test_url_ingestion_not_implemented_yet(client: TestClient) -> None:
    response = client.post("/ingest", json={"type": "url", "url": "https://example.com"})

    assert response.status_code == 501
    assert response.json()["error"]["code"] == "not_implemented"


def test_error_body_includes_request_id(client: TestClient) -> None:
    response = client.post("/ingest", json={"type": "note", "content": ""}, headers={"X-Request-ID": "req-42"})

    assert response.json()["error"]["request_id"] == "req-42"


class TestDeriveTitle:
    def test_uses_first_non_empty_line(self) -> None:
        assert derive_title("\n\n  First line  \nSecond") == "First line"

    def test_collapses_whitespace(self) -> None:
        assert derive_title("a   lot\tof   space") == "a lot of space"

    def test_truncates_long_lines_with_ellipsis(self) -> None:
        title = derive_title("word " * 50)

        assert len(title) <= 80
        assert title.endswith("…")
