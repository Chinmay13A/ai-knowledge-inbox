from fastapi.testclient import TestClient

from app.models.schemas import MAX_NOTE_CHARS


def test_oversized_body_is_rejected_before_parsing(client: TestClient) -> None:
    body = b'{"type": "note", "content": "' + b"x" * 1_100_000 + b'"}'

    response = client.post("/ingest", content=body, headers={"Content-Type": "application/json"})

    assert response.status_code == 413
    error = response.json()["error"]
    assert error["code"] == "payload_too_large"
    assert "1,000,000 bytes" in error["message"]
    assert error["request_id"] == response.headers["X-Request-ID"]


def test_largest_valid_note_is_accepted(client: TestClient) -> None:
    response = client.post("/ingest", json={"type": "note", "content": "é" * MAX_NOTE_CHARS})

    assert response.status_code == 201
