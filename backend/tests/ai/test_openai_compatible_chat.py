import asyncio
import json

import httpx
import pytest

from app.ai.llm.openai_compatible import OpenAICompatibleChatModel
from app.errors import LLMError

GROQ_URL = "https://api.groq.com/openai/v1"


def chat_reply(text: str | None, finish: str = "stop") -> dict:
    return {
        "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": finish}],
        "usage": {"prompt_tokens": 90, "completion_tokens": 12},
    }


class FakeServer:
    def __init__(self, reply: dict) -> None:
        self.reply = reply
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(200, json=self.reply)


def make(server, **overrides) -> OpenAICompatibleChatModel:  # noqa: ANN001, ANN003
    options = {"base_url": GROQ_URL, "model": "llama-3.3-70b-versatile", "max_retries": 0}
    options.update(overrides)
    return OpenAICompatibleChatModel(transport=httpx.MockTransport(server), **options)


def generate(model: OpenAICompatibleChatModel):  # noqa: ANN201
    return asyncio.run(model.generate(system="RULES", user="QUESTION"))


def test_request_to_chat_completions() -> None:
    server = FakeServer(chat_reply("Answer [1]"))

    completion = generate(make(server, api_key="gsk-test", temperature=0.2, max_output_tokens=300))

    request = server.requests[0]
    assert str(request.url) == f"{GROQ_URL}/chat/completions"
    assert request.headers["authorization"] == "Bearer gsk-test"
    assert json.loads(request.content) == {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "system", "content": "RULES"}, {"role": "user", "content": "QUESTION"}],
        "temperature": 0.2,
        "max_tokens": 300,
    }
    assert (completion.text, completion.input_tokens, completion.output_tokens) == ("Answer [1]", 90, 12)


def test_no_auth_header_without_key() -> None:
    server = FakeServer(chat_reply("ok"))

    generate(make(server, base_url="http://localhost:11434/v1"))

    assert "authorization" not in server.requests[0].headers


def test_length_finish_marks_truncated() -> None:
    assert generate(make(FakeServer(chat_reply("partial", finish="length")))).truncated is True


def test_content_filter_is_declined() -> None:
    with pytest.raises(LLMError, match="declined"):
        generate(make(FakeServer(chat_reply("", finish="content_filter"))))


@pytest.mark.parametrize(("reply", "message"), [({"choices": []}, "Unexpected response"), (chat_reply(None), "empty answer")])
def test_bad_replies(reply: dict, message: str) -> None:
    with pytest.raises(LLMError, match=message):
        generate(make(FakeServer(reply)))
