import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_response_includes_generated_request_id(client: TestClient) -> None:
    response = client.get("/health")

    assert response.headers.get("X-Request-ID")


def test_incoming_request_id_is_echoed(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "test-123"})

    assert response.headers["X-Request-ID"] == "test-123"
