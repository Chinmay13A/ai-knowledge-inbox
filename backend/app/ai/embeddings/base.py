"""The Embedder interface. Services depend only on this; concrete providers live next to it."""

from collections.abc import Iterator, Sequence
from typing import Protocol

import numpy as np

from app.errors import EmbeddingError


class Embedder(Protocol):
    # Identifies the vector space (provider + model + dimensions). Stored with every vector so
    # vectors from different models are never compared, and a config change triggers re-embedding.
    model_id: str

    async def embed_documents(self, texts: list[str]) -> list[np.ndarray]:
        """Embeds stored content (chunks). Returns unit-length float32 vectors, in input order."""
        ...

    async def embed_query(self, text: str) -> np.ndarray:
        """Embeds a search query (a user's question). Returns a unit-length float32 vector."""
        ...


class UnconfiguredEmbedder:
    """Stands in when no API key is set: the app still runs, and items fail with a clear message."""

    model_id = "unconfigured"
    MESSAGE = "Embeddings are not configured: set EMBEDDING_API_KEY in backend/.env"

    async def embed_documents(self, texts: list[str]) -> list[np.ndarray]:
        raise EmbeddingError(self.MESSAGE)

    async def embed_query(self, text: str) -> np.ndarray:
        raise EmbeddingError(self.MESSAGE)


def build_model_id(provider: str, model: str, dimensions: int | None) -> str:
    return f"{provider}:{model}@{dimensions or 'default'}"


def normalize(vectors: Sequence[Sequence[float]]) -> list[np.ndarray]:
    """float32, unit length, so cosine similarity is a plain dot product."""
    result = []
    for values in vectors:
        vector = np.asarray(values, dtype=np.float32)
        norm = float(np.linalg.norm(vector))
        result.append(vector / norm if norm > 0 else vector)
    return result


def batched(items: list[str], size: int) -> Iterator[list[str]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]
