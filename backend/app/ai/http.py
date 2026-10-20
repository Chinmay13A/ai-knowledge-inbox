"""Shared HTTP plumbing for AI providers: retries with backoff and readable error messages.

Every provider adapter (embeddings now, LLMs later) sends requests through `post_json`,
so retry behaviour, error wording and logging are identical across providers.
"""

import asyncio
import logging
import time
from typing import Any

import httpx

from app.errors import AIProviderError

RETRYABLE_STATUS = {429, 500, 502, 503, 504}
BACKOFF_BASE_S = 1.0
MAX_RETRY_AFTER_S = 30.0

logger = logging.getLogger(__name__)


async def post_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    json: dict[str, Any],
    headers: dict[str, str],
    provider: str,
    operation: str,
    max_retries: int,
    error_cls: type[AIProviderError] = AIProviderError,
) -> dict[str, Any]:
    """POST `json` and return the decoded response, retrying transient failures.

    Raises `error_cls` with a message that is safe to show to users (never includes keys or content).
    """
    for attempt in range(max_retries + 1):
        start = time.perf_counter()
        retry_after: float | None = None
        try:
            response = await client.post(url, json=json, headers=headers)
        except httpx.TimeoutException:
            failure = f"Could not reach {provider} (request timed out)"
        except httpx.TransportError:
            failure = f"Could not reach {provider}"
        else:
            logger.info(
                "ai.request",
                extra={
                    "provider": provider,
                    "operation": operation,
                    "status_code": response.status_code,
                    "attempt": attempt + 1,
                    "duration_ms": round((time.perf_counter() - start) * 1000, 2),
                },
            )
            if response.is_success:
                try:
                    return response.json()
                except ValueError:
                    raise error_cls(f"Unexpected response from {provider}") from None
            failure = error_message(provider, response)
            if response.status_code not in RETRYABLE_STATUS:
                raise error_cls(failure)
            retry_after = _retry_after_seconds(response)

        if attempt == max_retries:
            raise error_cls(failure)
        wait_s = retry_after if retry_after is not None else BACKOFF_BASE_S * 2**attempt
        logger.warning(
            "ai.retry",
            extra={
                "provider": provider,
                "operation": operation,
                "attempt": attempt + 1,
                "wait_s": wait_s,
                "reason": failure,
            },
        )
        await sleep(wait_s)

    raise AssertionError("unreachable")  # the loop always returns or raises


async def sleep(seconds: float) -> None:
    """Indirection so tests can skip real waiting."""
    await asyncio.sleep(seconds)


def error_message(provider: str, response: httpx.Response) -> str:
    status = response.status_code
    detail = _provider_detail(response)
    if status in (401, 403) or (status == 400 and "api key" in detail.lower()) or "API_KEY_INVALID" in response.text:
        return f"{provider} rejected the API key"
    if status == 429:
        return f"{provider} rate limit reached, try again shortly"
    return f"{provider} API error {status}: {detail}" if detail else f"{provider} API error {status}"


def _provider_detail(response: httpx.Response) -> str:
    """Best-effort short error message from the provider's JSON error body."""
    try:
        body = response.json()
    except ValueError:
        return response.text[:200].strip()
    error = body.get("error") if isinstance(body, dict) else None
    if isinstance(error, dict) and isinstance(error.get("message"), str):
        return error["message"][:200]
    if isinstance(error, str):
        return error[:200]
    return ""


def _retry_after_seconds(response: httpx.Response) -> float | None:
    try:
        value = float(response.headers.get("Retry-After", ""))
    except ValueError:
        return None
    return min(max(value, 0.0), MAX_RETRY_AFTER_S)
