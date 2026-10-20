import asyncio
import json

import httpx
import pytest

from app.ai.llm.gemini import GeminiChatModel
from app.errors import LLMError


def gemini_reply(*texts: str, finish: str = "STOP", **extra: object) -> dict:
    return {
        "candidates": [{"content": {"role": "model", "parts": [{"text": t} for t in texts]}, "finishReason": finish}],
        "usageMetadata": {"promptTokenCount": 120, "candidatesTokenCount": 15},
        **extra,
    }


class FakeGemini:
    def __init__(self, reply: dict) -> None:
        self.reply = reply
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(200, json=self.reply)


def make(handler, **overrides) -> GeminiChatModel:  # noqa: ANN001, ANN003
    options = {"api_key": "test-key", "model": "gemini-2.5-flash", "max_retries": 0, "thinking_budget": 0}
    options.update(overrides)
    return GeminiChatModel(transport=httpx.MockTransport(handler), **options)


def generate(model: GeminiChatModel):  # noqa: ANN201
    return asyncio.run(model.generate(system="SYSTEM RULES", user="Sources... Question: what?"))


def test_request_shape_and_key_in_header() -> None:
    fake = FakeGemini(gemini_reply("Hi [1]"))

    generate(make(fake, temperature=0.2, max_output_tokens=512))

    request = fake.requests[0]
    assert str(request.url) == "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    assert request.headers["x-goog-api-key"] == "test-key"
    assert "test-key" not in str(request.url)
    assert json.loads(request.content) == {
        "systemInstruction": {"parts": [{"text": "SYSTEM RULES"}]},
        "contents": [{"role": "user", "parts": [{"text": "Sources... Question: what?"}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 512, "thinkingConfig": {"thinkingBudget": 0}},
    }


def test_thinking_config_omitted_when_none() -> None:
    fake = FakeGemini(gemini_reply("ok"))

    generate(make(fake, thinking_budget=None))

    assert "thinkingConfig" not in json.loads(fake.requests[0].content)["generationConfig"]


def test_joins_parts_and_reads_usage() -> None:
    completion = generate(make(FakeGemini(gemini_reply("RAG retrieves ", "documents [1]."))))

    assert completion.text == "RAG retrieves documents [1]."
    assert (completion.input_tokens, completion.output_tokens, completion.truncated) == (120, 15, False)


def test_thought_parts_are_excluded() -> None:
    reply = gemini_reply("final answer")
    reply["candidates"][0]["content"]["parts"].insert(0, {"text": "internal reasoning", "thought": True})

    assert generate(make(FakeGemini(reply))).text == "final answer"


def test_max_tokens_marks_truncated() -> None:
    assert generate(make(FakeGemini(gemini_reply("partial", finish="MAX_TOKENS")))).truncated is True


@pytest.mark.parametrize(
    "reply",
    [
        gemini_reply("x", finish="SAFETY"),
        {"promptFeedback": {"blockReason": "SAFETY"}},
    ],
)
def test_blocked_answers(reply: dict) -> None:
    with pytest.raises(LLMError, match="declined to answer"):
        generate(make(FakeGemini(reply)))


@pytest.mark.parametrize("reply", [{"candidates": []}, gemini_reply("   ")])
def test_empty_answers(reply: dict) -> None:
    with pytest.raises(LLMError, match="empty answer"):
        generate(make(FakeGemini(reply)))


def test_invalid_key() -> None:
    error = {"error": {"code": 400, "message": "API key not valid. Please pass a valid API key."}}

    with pytest.raises(LLMError, match="Gemini rejected the API key"):
        generate(make(lambda request: httpx.Response(400, json=error)))


def test_model_id() -> None:
    assert make(FakeGemini(gemini_reply("x"))).model_id == "gemini:gemini-2.5-flash"
