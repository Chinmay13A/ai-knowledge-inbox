"""Text generation from any server speaking the OpenAI `/chat/completions` format.

Covers Groq, OpenAI, local Ollama / LM Studio, Together, Mistral and others.
"""

import httpx

from app.ai.http import post_json
from app.ai.llm.base import Completion
from app.errors import LLMError

PROVIDER = "LLM provider"


class OpenAICompatibleChatModel:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None = None,
        temperature: float = 0.2,
        max_output_tokens: int = 1024,
        timeout_s: float = 60.0,
        max_retries: int = 3,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.model_id = f"openai_compatible:{model}"
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._api_key = api_key
        self._model = model
        self._temperature = temperature
        self._max_output_tokens = max_output_tokens
        self._timeout_s = timeout_s
        self._max_retries = max_retries
        self._transport = transport

    def check_ready(self) -> None:
        """Configured adapters are always ready; failures surface on the actual call."""

    async def generate(self, *, system: str, user: str) -> Completion:
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        body = {
            "model": self._model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": self._temperature,
            "max_tokens": self._max_output_tokens,
        }
        async with httpx.AsyncClient(transport=self._transport, timeout=self._timeout_s) as client:
            data = await post_json(
                client,
                self._url,
                json=body,
                headers=headers,
                provider=PROVIDER,
                operation="generate",
                max_retries=self._max_retries,
                error_cls=LLMError,
            )
        return _parse(data)


def _parse(data: dict) -> Completion:
    try:
        choice = data["choices"][0]
        text = (choice["message"]["content"] or "").strip()
    except (KeyError, IndexError, TypeError):
        raise LLMError(f"Unexpected response from {PROVIDER}") from None
    if choice.get("finish_reason") == "content_filter":
        raise LLMError("The model declined to answer this question")
    if not text:
        raise LLMError("The model returned an empty answer")
    usage = data.get("usage") or {}
    return Completion(
        text=text,
        input_tokens=usage.get("prompt_tokens"),
        output_tokens=usage.get("completion_tokens"),
        truncated=choice.get("finish_reason") == "length",
    )
