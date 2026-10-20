from fastapi import FastAPI
from fastapi.testclient import TestClient


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


def test_unknown_route_uses_standard_error_format(client: TestClient) -> None:
    response = client.get("/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "http_error"


def test_unhandled_exception_returns_generic_500(app: FastAPI) -> None:
    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("secret internal detail")

    with TestClient(app) as client:
        response = client.get("/boom")

    error = response.json()["error"]
    assert response.status_code == 500
    assert error["code"] == "internal_error"
    assert "secret" not in error["message"]
    assert error["request_id"] == response.headers["X-Request-ID"]
