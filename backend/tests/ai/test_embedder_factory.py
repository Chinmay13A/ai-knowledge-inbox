import asyncio

import pytest
from pydantic import ValidationError

from app.ai.embeddings.base import UnconfiguredEmbedder
from app.ai.embeddings.factory import build_embedder
from app.ai.embeddings.gemini import GeminiEmbedder
from app.ai.embeddings.openai_compatible import OpenAICompatibleEmbedder
from app.config import Settings
from app.errors import AINotConfiguredError


def settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_gemini_is_the_default_provider() -> None:
    embedder = build_embedder(settings(embedding_api_key="key"))

    assert isinstance(embedder, GeminiEmbedder)
    assert embedder.model_id == "gemini:gemini-embedding-001@768"


def test_switching_to_openai_is_config_only() -> None:
    embedder = build_embedder(
        settings(
            embedding_provider="openai_compatible",
            embedding_base_url="https://api.openai.com/v1",
            embedding_model="text-embedding-3-small",
            embedding_dimensions=None,
            embedding_api_key="sk-test",
        )
    )

    assert isinstance(embedder, OpenAICompatibleEmbedder)
    assert embedder.model_id == "openai_compatible:text-embedding-3-small@default"


def test_local_server_needs_no_key() -> None:
    embedder = build_embedder(
        settings(embedding_provider="openai_compatible", embedding_base_url="http://localhost:11434/v1")
    )

    assert isinstance(embedder, OpenAICompatibleEmbedder)


def test_missing_gemini_key_gives_unconfigured_embedder() -> None:
    embedder = build_embedder(settings())

    assert isinstance(embedder, UnconfiguredEmbedder)
    with pytest.raises(AINotConfiguredError, match="set EMBEDDING_API_KEY"):
        asyncio.run(embedder.embed_documents(["a"]))


@pytest.mark.parametrize(
    "overrides",
    [
        {"embedding_provider": "cohere"},
        {"embedding_provider": "openai_compatible"},  # missing base URL
        {"embedding_batch_size": 0},
    ],
)
def test_invalid_embedding_settings_fail_fast(overrides: dict) -> None:
    with pytest.raises(ValidationError):
        settings(**overrides)


def test_api_key_is_never_printed() -> None:
    configured = settings(embedding_api_key="super-secret")

    assert "super-secret" not in repr(configured)
    assert "super-secret" not in str(configured.model_dump())
