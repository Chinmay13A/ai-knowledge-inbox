"""The only place that knows the concrete embedder classes: config in, Embedder out."""

import logging

from app.ai.embeddings.base import Embedder, UnconfiguredEmbedder
from app.ai.embeddings.gemini import GeminiEmbedder
from app.ai.embeddings.openai_compatible import OpenAICompatibleEmbedder
from app.config import Settings

logger = logging.getLogger(__name__)


def build_embedder(settings: Settings) -> Embedder:
    api_key = settings.embedding_api_key.get_secret_value() if settings.embedding_api_key else None
    common = {
        "model": settings.embedding_model,
        "dimensions": settings.embedding_dimensions,
        "batch_size": settings.embedding_batch_size,
        "timeout_s": settings.embedding_timeout_s,
        "max_retries": settings.embedding_max_retries,
    }

    if settings.embedding_provider == "gemini":
        if not api_key:
            logger.warning("embedder.not_configured", extra={"provider": "gemini"})
            return UnconfiguredEmbedder()
        embedder: Embedder = GeminiEmbedder(api_key=api_key, **common)
    else:  # openai_compatible; settings validation guarantees a base URL. The key is optional (e.g. Ollama).
        embedder = OpenAICompatibleEmbedder(base_url=settings.embedding_base_url or "", api_key=api_key, **common)

    logger.info("embedder.configured", extra={"model_id": embedder.model_id})
    return embedder
