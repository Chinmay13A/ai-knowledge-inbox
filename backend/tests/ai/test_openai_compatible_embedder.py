import asyncio
import json

import httpx
import numpy as np

from app.ai.embeddings.openai_compatible import OpenAICompatibleEmbedder


class FakeServer:
    """Answers like an OpenAI-compatible /embeddings endpoint, deliberately out of order."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        inputs = json.loads(request.content)["input"]
        data = [{"index": i, "embedding": [float(i + 1), 0.0]} for i in range(len(inputs))]
        return httpx.Response(200, json={"data": data[::-1]})


def make(server: FakeServer, **overrides) -> OpenAICompatibleEmbedder:  # noqa: ANN003
    options = {"base_url": "http://localhost:11434/v1/", "model": "nomic-embed-text", "max_retries": 0}
    options.update(overrides)
    return OpenAICompatibleEmbedder(transport=httpx.MockTransport(server), **options)


def test_posts_to_embeddings_endpoint_and_restores_order() -> None:
    server = FakeServer()

    vectors = asyncio.run(make(server).embed_documents(["a", "b", "c"]))

    assert str(server.requests[0].url) == "http://localhost:11434/v1/embeddings"
    assert json.loads(server.requests[0].content) == {"model": "nomic-embed-text", "input": ["a", "b", "c"]}
    assert len(vectors) == 3
    assert all(np.allclose(vector, [1.0, 0.0]) for vector in vectors)  # sorted by index, then normalized


def test_bearer_header_only_when_key_is_set() -> None:
    server = FakeServer()

    asyncio.run(make(server).embed_query("q"))
    asyncio.run(make(server, api_key="sk-test").embed_query("q"))

    assert "authorization" not in server.requests[0].headers
    assert server.requests[1].headers["authorization"] == "Bearer sk-test"


def test_dimensions_sent_only_when_configured() -> None:
    server = FakeServer()

    asyncio.run(make(server).embed_documents(["a"]))
    asyncio.run(make(server, dimensions=256).embed_documents(["a"]))

    assert "dimensions" not in json.loads(server.requests[0].content)
    assert json.loads(server.requests[1].content)["dimensions"] == 256
