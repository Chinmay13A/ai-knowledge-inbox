import asyncio

import httpx
import pytest

from app.ai import http as ai_http
from app.errors import AIProviderError, EmbeddingError


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    waits: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        waits.append(seconds)

    monkeypatch.setattr(ai_http, "sleep", fake_sleep)
    return waits


def post(responses: list, max_retries: int = 3, error_cls: type[AIProviderError] = AIProviderError) -> dict:
    queue = list(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        result = queue.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    async def run() -> dict:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await ai_http.post_json(
                client,
                "https://ai.example/v1/embed",
                json={},
                headers={},
                provider="Acme",
                operation="embed",
                max_retries=max_retries,
                error_cls=error_cls,
            )

    return asyncio.run(run())


def test_success_returns_json() -> None:
    assert post([httpx.Response(200, json={"ok": True})]) == {"ok": True}


def test_retries_transient_errors_with_backoff(no_waiting: list[float]) -> None:
    result = post([httpx.Response(429), httpx.Response(503), httpx.Response(200, json={"ok": 1})])

    assert result == {"ok": 1}
    assert no_waiting == [1.0, 2.0]


def test_honours_retry_after(no_waiting: list[float]) -> None:
    post([httpx.Response(429, headers={"Retry-After": "7"}), httpx.Response(200, json={})])

    assert no_waiting == [7.0]


def test_gives_up_after_max_retries() -> None:
    with pytest.raises(AIProviderError, match="Acme rate limit reached"):
        post([httpx.Response(429)] * 4)


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (httpx.Response(401), "Acme rejected the API key"),
        (httpx.Response(403), "Acme rejected the API key"),
        (
            httpx.Response(400, json={"error": {"message": "API key not valid. Please pass a valid API key."}}),
            "Acme rejected the API key",
        ),
        (httpx.Response(400, json={"error": {"message": "Bad model name"}}), "Acme API error 400: Bad model name"),
        (httpx.Response(404, text="not here"), "Acme API error 404: not here"),
    ],
)
def test_non_retryable_errors_fail_fast(response: httpx.Response, message: str, no_waiting: list[float]) -> None:
    with pytest.raises(AIProviderError) as exc_info:
        post([response])

    assert exc_info.value.message == message
    assert no_waiting == []


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (httpx.ReadTimeout("slow"), "Could not reach Acme (request timed out)"),
        (httpx.ConnectError("down"), "Could not reach Acme"),
    ],
)
def test_network_errors(error: Exception, message: str) -> None:
    with pytest.raises(AIProviderError) as exc_info:
        post([error], max_retries=0)

    assert exc_info.value.message == message


def test_invalid_json_body() -> None:
    with pytest.raises(AIProviderError, match="Unexpected response from Acme"):
        post([httpx.Response(200, text="<html>")])


def test_uses_requested_error_class() -> None:
    with pytest.raises(EmbeddingError):
        post([httpx.Response(401)], error_cls=EmbeddingError)
