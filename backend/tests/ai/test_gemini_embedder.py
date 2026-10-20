import asyncio
import json

import httpx
import numpy as np
import pytest

from app.ai.embeddings.gemini import GeminiEmbedder
from app.errors import EmbeddingError


class FakeGemini:
    """Mock transport handler that answers batchEmbedContents like the real API."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        body = json.loads(request.content)
        # First value encodes the input length, so tests can check ordering.
        embeddings = [{"values": [float(len(r["content"]["parts"][0]["text"])), 1.0, 1.0]} for r in body["requests"]]
        return httpx.Response(200, json={"embeddings": embeddings})

    def bodies(self) -> list[dict]:
        return [json.loads(r.content) for r in self.requests]


def make(handler, **overrides) -> GeminiEmbedder:  # noqa: ANN001
    options = {"api_key": "test-key", "model": "gemini-embedding-001", "dimensions": 768, "max_retries": 0}
    options.update(overrides)
    return GeminiEmbedder(transport=httpx.MockTransport(handler), **options)


def test_batches_and_preserves_order() -> None:
    fake = FakeGemini()
    texts = ["x" * (i + 1) for i in range(120)]

    vectors = asyncio.run(make(fake, batch_size=50).embed_documents(texts))

    assert [len(body["requests"]) for body in fake.bodies()] == [50, 50, 20]
    assert len(vectors) == 120
    for length, vector in zip((1, 60, 120), (vectors[0], vectors[59], vectors[119]), strict=True):
        expected = np.array([length, 1.0, 1.0]) / np.linalg.norm([length, 1.0, 1.0])
        assert np.allclose(vector, expected)


def test_request_shape_and_key_in_header() -> None:
    fake = FakeGemini()

    asyncio.run(make(fake).embed_documents(["hello"]))

    request = fake.requests[0]
    assert str(request.url) == (
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:batchEmbedContents"
    )
    assert request.headers["x-goog-api-key"] == "test-key"
    assert "test-key" not in str(request.url)
    assert fake.bodies()[0]["requests"][0] == {
        "model": "models/gemini-embedding-001",
        "content": {"parts": [{"text": "hello"}]},
        "taskType": "RETRIEVAL_DOCUMENT",
        "outputDimensionality": 768,
    }


def test_query_uses_retrieval_query_task() -> None:
    fake = FakeGemini()

    asyncio.run(make(fake).embed_query("what is rag?"))

    assert fake.bodies()[0]["requests"][0]["taskType"] == "RETRIEVAL_QUERY"


def test_vectors_are_unit_length_float32() -> None:
    vectors = asyncio.run(make(FakeGemini()).embed_documents(["abc", "abcdef"]))

    for vector in vectors:
        assert vector.dtype == np.float32
        assert np.isclose(np.linalg.norm(vector), 1.0, atol=1e-6)


def test_dimensions_omitted_when_not_configured() -> None:
    fake = FakeGemini()

    asyncio.run(make(fake, dimensions=None).embed_documents(["a"]))

    assert "outputDimensionality" not in fake.bodies()[0]["requests"][0]


@pytest.mark.parametrize("body", [{"nope": []}, {"embeddings": [{"values": [1.0]}, {"values": [1.0]}]}])
def test_malformed_response(body: dict) -> None:
    with pytest.raises(EmbeddingError, match="Unexpected response from Gemini"):
        asyncio.run(make(lambda request: httpx.Response(200, json=body)).embed_documents(["only one"]))


def test_invalid_key_message() -> None:
    error = {
        "error": {
            "code": 400,
            "message": "API key not valid. Please pass a valid API key.",
            "status": "INVALID_ARGUMENT",
        }
    }

    with pytest.raises(EmbeddingError, match="Gemini rejected the API key"):
        asyncio.run(make(lambda request: httpx.Response(400, json=error)).embed_documents(["a"]))


def test_model_id_includes_provider_model_and_dimensions() -> None:
    assert make(FakeGemini()).model_id == "gemini:gemini-embedding-001@768"
    assert make(FakeGemini(), dimensions=None).model_id == "gemini:gemini-embedding-001@default"
