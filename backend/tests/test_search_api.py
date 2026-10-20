import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.ai.embeddings.base import UnconfiguredEmbedder
from app.errors import EmbeddingError
from tests.conftest import FakeEmbedder, add_note


def search(client: TestClient, query: str, **extra: object):  # noqa: ANN201
    return client.post("/search", json={"query": query, **extra})


@pytest.fixture
def inbox(client: TestClient) -> dict[str, int]:
    notes = {
        "rag": "Retrieval augmented generation passes retrieved chunks to the model.",
        "groceries": "Buy milk, eggs and bread.",
        "travel": "Train to Pune at nine.",
    }
    return {name: add_note(client, text)["id"] for name, text in notes.items()}


def test_returns_ranked_results(client: TestClient, inbox: dict[str, int], app: FastAPI) -> None:
    app.state.settings.retrieval_min_score = -1.0

    response = search(client, "  what is retrieval augmented generation?  ")

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "what is retrieval augmented generation?"
    top = body["results"][0]
    assert top["item_id"] == inbox["rag"]
    assert set(top) == {"item_id", "item_title", "item_url", "source_type", "chunk_index", "text", "score"}
    assert top["source_type"] == "note"


def test_top_k_from_request_overrides_default(client: TestClient, inbox: dict[str, int], app: FastAPI) -> None:
    app.state.settings.retrieval_min_score = -1.0

    assert len(search(client, "milk", top_k=1).json()["results"]) == 1
    assert len(search(client, "milk").json()["results"]) == 3  # default top_k is 5, inbox has 3


def test_no_matches_is_an_empty_list(client: TestClient) -> None:
    response = search(client, "anything at all")

    assert response.status_code == 200
    assert response.json()["results"] == []


@pytest.mark.parametrize(
    "payload",
    [{"query": "   "}, {"query": "x" * 1_001}, {"query": "ok", "top_k": 0}, {"query": "ok", "top_k": 21}, {}],
)
def test_invalid_requests_are_rejected(client: TestClient, payload: dict) -> None:
    response = client.post("/search", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_provider_failure_is_502(client: TestClient, inbox: dict[str, int], embedder: FakeEmbedder) -> None:
    embedder.error = EmbeddingError("Gemini rate limit reached, try again shortly")

    response = search(client, "milk")

    assert response.status_code == 502
    assert response.json()["error"] == {
        "code": "embedding_failed",
        "message": "Gemini rate limit reached, try again shortly",
        "request_id": response.headers["X-Request-ID"],
    }


def test_missing_api_key_is_503(app: FastAPI) -> None:
    app.state.embedder = UnconfiguredEmbedder()

    with TestClient(app) as client:
        response = search(client, "anything")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "ai_not_configured"
    assert "set EMBEDDING_API_KEY" in response.json()["error"]["message"]
