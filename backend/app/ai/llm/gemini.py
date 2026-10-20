"""Google Gemini text generation via the REST API (`generateContent`)."""

import httpx

from app.ai.http import post_json
from app.ai.llm.base import Completion
from app.errors import LLMError

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta"
PROVIDER = "Gemini"
BLOCKED_FINISH_REASONS = {"SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII"}


class GeminiChatModel:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        temperature: float = 0.2,
        max_output_tokens: int = 1024,
        timeout_s: float = 60.0,
        max_retries: int = 3,
        thinking_budget: int | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.model_id = f"gemini:{model}"
        self._api_key = api_key
        self._model = model
        self._temperature = temperature
        self._max_output_tokens = max_output_tokens
        self._timeout_s = timeout_s
        self._max_retries = max_retries
        self._thinking_budget = thinking_budget
        self._transport = transport

    def check_ready(self) -> None:
        """Configured adapters are always ready; failures surface on the actual call."""

    async def generate(self, *, system: str, user: str) -> Completion:
        generation_config: dict = {"temperature": self._temperature, "maxOutputTokens": self._max_output_tokens}
        if self._thinking_budget is not None:
            generation_config["thinkingConfig"] = {"thinkingBudget": self._thinking_budget}
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": generation_config,
        }
        async with httpx.AsyncClient(transport=self._transport, timeout=self._timeout_s) as client:
            data = await post_json(
                client,
                f"{GEMINI_API_URL}/models/{self._model}:generateContent",
                json=body,
                headers={"x-goog-api-key": self._api_key},  # header, never the URL: keeps the key out of logs
                provider=PROVIDER,
                operation="generate",
                max_retries=self._max_retries,
                error_cls=LLMError,
            )
        return _parse(data)


def _parse(data: dict) -> Completion:
    if not isinstance(data, dict):
        raise LLMError(f"Unexpected response from {PROVIDER}")
    if (data.get("promptFeedback") or {}).get("blockReason"):
        raise LLMError("The model declined to answer this question")

    candidates = data.get("candidates") or []
    if not candidates or not isinstance(candidates[0], dict):
        raise LLMError("The model returned an empty answer")
    candidate = candidates[0]
    finish_reason = candidate.get("finishReason")
    if finish_reason in BLOCKED_FINISH_REASONS:
        raise LLMError("The model declined to answer this question")

    parts = (candidate.get("content") or {}).get("parts") or []
    text = "".join(part.get("text", "") for part in parts if isinstance(part, dict) and not part.get("thought")).strip()
    if not text:
        raise LLMError("The model returned an empty answer")

    usage = data.get("usageMetadata") or {}
    return Completion(
        text=text,
        input_tokens=usage.get("promptTokenCount"),
        output_tokens=usage.get("candidatesTokenCount"),
        truncated=finish_reason == "MAX_TOKENS",
    )
