import pytest
from fastapi.testclient import TestClient

from app.errors import (
    EmptyContentError,
    RobotsDisallowedError,
    UnsupportedContentError,
    UrlFetchError,
    UrlFetchTimeoutError,
    UrlNotAllowedError,
)
from app.models.schemas import MAX_NOTE_CHARS
from app.services.fetcher import FetchedPage
from app.services.ingest_service import derive_title
from tests.conftest import StubFetcher, add_note


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


class TestUrlIngestion:
    def test_url_is_fetched_and_stored(self, client: TestClient, fetcher: StubFetcher) -> None:
        fetcher.result = FetchedPage(
            url="https://example.com/rag", title="What is RAG?", text="RAG combines retrieval with generation."
        )

        response = client.post("/ingest", json={"type": "url", "url": "https://example.com/rag"})

        assert response.status_code == 201
        item = response.json()
        assert item["source_type"] == "url"
        assert item["url"] == "https://example.com/rag"
        assert item["title"] == "What is RAG?"
        assert item["preview"] == "RAG combines retrieval with generation."
        assert fetcher.requested == ["https://example.com/rag"]
        assert client.get("/items").json()["items"][0]["id"] == item["id"]

    def test_stores_final_url_after_redirects(self, client: TestClient, fetcher: StubFetcher) -> None:
        fetcher.result = FetchedPage(url="https://www.example.com/final", title="T", text="Body")

        item = client.post("/ingest", json={"type": "url", "url": "https://example.com/start"}).json()

        assert item["url"] == "https://www.example.com/final"

    def test_title_falls_back_to_first_line(self, client: TestClient, fetcher: StubFetcher) -> None:
        fetcher.result = FetchedPage(url="https://example.com", title=None, text="First line\nMore text")

        item = client.post("/ingest", json={"type": "url", "url": "https://example.com"}).json()

        assert item["title"] == "First line"

    def test_invalid_url_is_rejected_before_fetching(self, client: TestClient, fetcher: StubFetcher) -> None:
        response = client.post("/ingest", json={"type": "url", "url": "not a url"})

        assert response.status_code == 422
        assert fetcher.requested == []

    @pytest.mark.parametrize(
        ("error", "status", "code"),
        [
            (UrlNotAllowedError("private"), 422, "url_not_allowed"),
            (RobotsDisallowedError("robots"), 422, "blocked_by_robots"),
            (UnsupportedContentError("pdf"), 422, "unsupported_content"),
            (EmptyContentError("empty"), 422, "empty_content"),
            (UrlFetchError("Site responded with 404"), 502, "url_fetch_failed"),
            (UrlFetchTimeoutError("slow"), 504, "url_fetch_timeout"),
        ],
    )
    def test_fetch_errors_map_to_status_and_store_nothing(
        self, client: TestClient, fetcher: StubFetcher, error: Exception, status: int, code: str
    ) -> None:
        fetcher.result = error

        response = client.post("/ingest", json={"type": "url", "url": "https://example.com"})

        assert response.status_code == status
        assert response.json()["error"]["code"] == code
        assert response.json()["error"]["message"] == str(error)
        assert client.get("/items").json()["total"] == 0


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
