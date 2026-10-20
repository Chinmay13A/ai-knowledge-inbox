"""Request middleware: request IDs, timing and one structured log line per request."""

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.errors import internal_error_response, payload_too_large_response
from app.request_context import request_id_var

REQUEST_ID_HEADER = "X-Request-ID"

logger = logging.getLogger("app.request")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        request.state.request_id = request_id
        request_id_var.set(request_id)
        log_fields = {"request_id": request_id, "method": request.method, "path": request.url.path}
        start = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            # Last line of defence: log the stack trace, return a generic 500 in the standard format.
            logger.exception(
                "request.failed",
                extra={**log_fields, "status_code": 500, "duration_ms": _elapsed_ms(start)},
            )
            response = internal_error_response(request_id)
            response.headers[REQUEST_ID_HEADER] = request_id
            return response

        response.headers[REQUEST_ID_HEADER] = request_id
        logger.log(
            _level_for(response.status_code),
            "request.completed",
            extra={**log_fields, "status_code": response.status_code, "duration_ms": _elapsed_ms(start)},
        )
        return response


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Rejects oversized bodies (by Content-Length) before anything reads them into memory."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        declared = request.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > self.max_bytes:
            return payload_too_large_response(getattr(request.state, "request_id", None), self.max_bytes)
        return await call_next(request)


def _level_for(status_code: int) -> int:
    if status_code >= 500:
        return logging.ERROR
    if status_code >= 400:
        return logging.WARNING
    return logging.INFO


def _elapsed_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 2)
