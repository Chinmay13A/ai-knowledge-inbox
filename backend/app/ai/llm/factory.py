"""The only place that knows the concrete chat model classes: config in, ChatModel out."""

import logging

from app.ai.llm.base import ChatModel, UnconfiguredChatModel
from app.ai.llm.gemini import GeminiChatModel
from app.ai.llm.openai_compatible import OpenAICompatibleChatModel
from app.config import Settings

logger = logging.getLogger(__name__)


def build_chat_model(settings: Settings) -> ChatModel:
    api_key = settings.llm_api_key_value()
    common = {
        "model": settings.llm_model,
        "temperature": settings.llm_temperature,
        "max_output_tokens": settings.llm_max_output_tokens,
        "timeout_s": settings.llm_timeout_s,
        "max_retries": settings.llm_max_retries,
    }

    if settings.llm_provider == "gemini":
        if not api_key:
            logger.warning("llm.not_configured", extra={"provider": "gemini"})
            return UnconfiguredChatModel()
        model: ChatModel = GeminiChatModel(api_key=api_key, thinking_budget=settings.llm_thinking_budget, **common)
    else:  # openai_compatible; settings validation guarantees a base URL. The key is optional (e.g. Ollama).
        model = OpenAICompatibleChatModel(base_url=settings.llm_base_url or "", api_key=api_key, **common)

    logger.info("llm.configured", extra={"model_id": model.model_id})
    return model
