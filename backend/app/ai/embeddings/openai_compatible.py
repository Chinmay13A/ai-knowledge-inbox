"""Embeddings from any server speaking the OpenAI `/embeddings` format.

Covers OpenAI itself, local Ollama / LM Studio, and hosted providers such as Together or Mistral.
"""

import httpx
import numpy as np

from app.ai.embeddings.base import batched, build_model_id, normalize
from app.ai.http import post_json
from app.errors import EmbeddingError

PROVIDER = "Embedding provider"


class OpenAICompatibleEmbedder:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None = None,
        dimensions: int | None = None,
        batch_size: int = 50,
        timeout_s: float = 30.0,
        max_retries: int = 3,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.model_id = build_model_id("openai_compatible", model, dimensions)
        self._url = f"{base_url.rstrip('/')}/embeddings"
        self._api_key = api_key
        self._model = model
        self._dimensions = dimensions
        self._batch_size = batch_size
        self._timeout_s = timeout_s
        self._max_retries = max_retries
        self._transport = transport

    def check_ready(self) -> None:
        """Configured adapters are always ready; failures surface on the actual call."""

    # The OpenAI format has no query/document distinction, so both use the same call.
    async def embed_documents(self, texts: list[str]) -> list[np.ndarray]:
        return await self._embed(texts)

    async def embed_query(self, text: str) -> np.ndarray:
        return (await self._embed([text]))[0]

    async def _embed(self, texts: list[str]) -> list[np.ndarray]:
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        vectors: list[list[float]] = []
        async with httpx.AsyncClient(transport=self._transport, timeout=self._timeout_s) as client:
            for batch in batched(texts, self._batch_size):
                body: dict = {"model": self._model, "input": batch}
                if self._dimensions:
                    body["dimensions"] = self._dimensions
                data = await post_json(
                    client,
                    self._url,
                    json=body,
                    headers=headers,
                    provider=PROVIDER,
                    operation="embed",
                    max_retries=self._max_retries,
                    error_cls=EmbeddingError,
                )
                vectors.extend(_parse(data, expected=len(batch)))
        return normalize(vectors)


def _parse(data: dict, *, expected: int) -> list[list[float]]:
    try:
        rows = sorted(data["data"], key=lambda row: row["index"])
        values = [row["embedding"] for row in rows]
    except (KeyError, TypeError):
        raise EmbeddingError(f"Unexpected response from {PROVIDER}") from None
    if len(values) != expected:
        raise EmbeddingError(f"Unexpected response from {PROVIDER}")
    return values
