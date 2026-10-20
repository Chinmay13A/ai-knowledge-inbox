import pytest
from pydantic import ValidationError

from app.ai.llm.base import UnconfiguredChatModel
from app.ai.llm.factory import build_chat_model
from app.ai.llm.gemini import GeminiChatModel
from app.ai.llm.openai_compatible import OpenAICompatibleChatModel
from app.config import Settings
from app.errors import AINotConfiguredError


def settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_gemini_reuses_the_embedding_key_by_default() -> None:
    model = build_chat_model(settings(embedding_api_key="shared-key"))

    assert isinstance(model, GeminiChatModel)
    assert model.model_id == "gemini:gemini-3.5-flash"


def test_explicit_llm_key_wins() -> None:
    configured = settings(embedding_api_key="embedding-key", llm_api_key="llm-key")

    assert configured.llm_api_key_value() == "llm-key"


def test_switching_to_groq_is_config_only() -> None:
    model = build_chat_model(
        settings(
            llm_provider="openai_compatible",
            llm_base_url="https://api.groq.com/openai/v1",
            llm_model="llama-3.3-70b-versatile",
            llm_api_key="gsk-test",
        )
    )

    assert isinstance(model, OpenAICompatibleChatModel)
    assert model.model_id == "openai_compatible:llama-3.3-70b-versatile"


def test_embedding_key_is_not_reused_across_providers() -> None:
    configured = settings(
        embedding_api_key="gemini-key", llm_provider="openai_compatible", llm_base_url="https://api.groq.com/openai/v1"
    )

    assert configured.llm_api_key_value() is None


def test_no_key_gives_unconfigured_model() -> None:
    model = build_chat_model(settings())

    assert isinstance(model, UnconfiguredChatModel)
    with pytest.raises(AINotConfiguredError, match="set LLM_API_KEY"):
        model.check_ready()


@pytest.mark.parametrize(
    "overrides",
    [
        {"llm_provider": "anthropic"},
        {"llm_provider": "openai_compatible"},  # missing base URL
        {"llm_temperature": 3.0},
        {"llm_max_output_tokens": 10},
    ],
)
def test_invalid_llm_settings_fail_fast(overrides: dict) -> None:
    with pytest.raises(ValidationError):
        settings(**overrides)


def test_llm_key_is_never_printed() -> None:
    configured = settings(llm_api_key="super-secret-llm")

    assert "super-secret-llm" not in repr(configured)
