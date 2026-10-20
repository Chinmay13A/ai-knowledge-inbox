import logging
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.ai.embeddings.base import UnconfiguredEmbedder
from app.ai.llm.base import UnconfiguredChatModel
from app.errors import UrlFetchError


def test_health_reports_readiness(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok", "embeddings": "ready", "llm": "ready"}


def test_health_reports_missing_ai_configuration(app: FastAPI) -> None:
    app.state.embedder = UnconfiguredEmbedder()
    app.state.chat_model = UnconfiguredChatModel()

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200  # missing keys are reported, not fatal
    assert response.json()["embeddings"] == "not_configured"
    assert response.json()["llm"] == "not_configured"


def test_health_is_503_when_database_is_unreachable(client: TestClient, app: FastAPI, tmp_path: Path) -> None:
    app.state.settings.db_path = str(tmp_path / "missing-dir" / "inbox.db")  # parent folder doesn't exist

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert response.json()["database"] == "error"


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


@pytest.mark.parametrize(("path", "level"), [("/health", logging.INFO), ("/does-not-exist", logging.WARNING)])
def test_request_log_level_follows_status(
    client: TestClient, caplog: pytest.LogCaptureFixture, path: str, level: int
) -> None:
    with caplog.at_level(logging.INFO, logger="app.request"):
        client.get(path)

    record = next(r for r in caplog.records if r.getMessage() == "request.completed")
    assert record.levelno == level


def test_server_errors_are_logged_as_errors(app: FastAPI, caplog: pytest.LogCaptureFixture) -> None:
    @app.get("/teapot-failure")
    def failing() -> None:
        raise UrlFetchError("Site responded with 500")  # a handled 502

    with TestClient(app) as client, caplog.at_level(logging.INFO, logger="app.request"):
        client.get("/teapot-failure")

    record = next(r for r in caplog.records if r.getMessage() == "request.completed")
    assert record.levelno == logging.ERROR
