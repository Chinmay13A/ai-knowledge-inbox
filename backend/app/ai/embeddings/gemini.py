"""Google Gemini embeddings via the REST API (`batchEmbedContents`)."""

import httpx
import numpy as np

from app.ai.embeddings.base import batched, build_model_id, normalize
from app.ai.http import post_json
from app.errors import EmbeddingError

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta"
PROVIDER = "Gemini"


class GeminiEmbedder:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        dimensions: int | None,
        batch_size: int = 50,
        timeout_s: float = 30.0,
        max_retries: int = 3,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.model_id = build_model_id("gemini", model, dimensions)
        self._api_key = api_key
        self._model = model
        self._dimensions = dimensions
        self._batch_size = batch_size
        self._timeout_s = timeout_s
        self._max_retries = max_retries
        self._transport = transport

    async def embed_documents(self, texts: list[str]) -> list[np.ndarray]:
        return await self._embed(texts, task_type="RETRIEVAL_DOCUMENT")

    async def embed_query(self, text: str) -> np.ndarray:
        return (await self._embed([text], task_type="RETRIEVAL_QUERY"))[0]

    async def _embed(self, texts: list[str], *, task_type: str) -> list[np.ndarray]:
        vectors: list[list[float]] = []
        async with httpx.AsyncClient(transport=self._transport, timeout=self._timeout_s) as client:
            for batch in batched(texts, self._batch_size):
                data = await post_json(
                    client,
                    f"{GEMINI_API_URL}/models/{self._model}:batchEmbedContents",
                    json={"requests": [self._request(text, task_type) for text in batch]},
                    headers={"x-goog-api-key": self._api_key},  # header, never the URL: keeps the key out of logs
                    provider=PROVIDER,
                    operation="embed",
                    max_retries=self._max_retries,
                    error_cls=EmbeddingError,
                )
                vectors.extend(_parse(data, expected=len(batch)))
        return normalize(vectors)

    def _request(self, text: str, task_type: str) -> dict:
        request = {"model": f"models/{self._model}", "content": {"parts": [{"text": text}]}, "taskType": task_type}
        if self._dimensions:
            request["outputDimensionality"] = self._dimensions
        return request


def _parse(data: dict, *, expected: int) -> list[list[float]]:
    try:
        values = [embedding["values"] for embedding in data["embeddings"]]
    except (KeyError, TypeError):
        raise EmbeddingError(f"Unexpected response from {PROVIDER}") from None
    if len(values) != expected:
        raise EmbeddingError(f"Unexpected response from {PROVIDER}")
    return values
