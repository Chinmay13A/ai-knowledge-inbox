"""The ChatModel interface. Services depend only on this; concrete providers live next to it."""

from dataclasses import dataclass
from typing import Protocol

from app.errors import AINotConfiguredError


@dataclass(frozen=True)
class Completion:
    text: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    truncated: bool = False  # the model stopped at the output token limit


class ChatModel(Protocol):
    model_id: str  # provider + model, e.g. "gemini:gemini-3.5-flash" (returned to clients and logged)

    def check_ready(self) -> None:
        """Raises AINotConfiguredError if this model cannot be used at all (e.g. no API key)."""
        ...

    async def generate(self, *, system: str, user: str) -> Completion:
        """One-shot generation: a system instruction plus a single user message."""
        ...


class UnconfiguredChatModel:
    """Stands in when no API key is set: the app still runs, and /query explains what to configure."""

    model_id = "unconfigured"
    MESSAGE = "Answer generation is not configured: set LLM_API_KEY (or EMBEDDING_API_KEY) in backend/.env"

    def check_ready(self) -> None:
        raise AINotConfiguredError(self.MESSAGE)

    async def generate(self, *, system: str, user: str) -> Completion:
        raise AINotConfiguredError(self.MESSAGE)
