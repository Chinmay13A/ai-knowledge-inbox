"""Application exceptions and the single error response format used by the API.

Every error body looks like: {"error": {"code", "message", "details"?, "request_id"}}
"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

# Location prefixes FastAPI adds that mean nothing to API clients.
_LOC_PREFIXES = {"body", "query", "path", "header"}
# Tags FastAPI inserts into error locations for the discriminated IngestRequest union.
_UNION_TAGS = {"note", "url"}


class AppError(Exception):
    status_code = 500
    code = "internal_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ItemNotFoundError(AppError):
    status_code = 404
    code = "item_not_found"


class UrlNotAllowedError(AppError):
    status_code = 422
    code = "url_not_allowed"


class RobotsDisallowedError(AppError):
    status_code = 422
    code = "blocked_by_robots"


class UnsupportedContentError(AppError):
    status_code = 422
    code = "unsupported_content"


class EmptyContentError(AppError):
    status_code = 422
    code = "empty_content"


class UrlFetchError(AppError):
    status_code = 502
    code = "url_fetch_failed"


class UrlFetchTimeoutError(AppError):
    status_code = 504
    code = "url_fetch_timeout"


def error_response(
    request_id: str | None,
    status_code: int,
    code: str,
    message: str,
    details: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    error: dict[str, Any] = {"code": code, "message": message, "request_id": request_id}
    if details:
        error["details"] = details
    return JSONResponse(status_code=status_code, content={"error": error})


def internal_error_response(request_id: str | None) -> JSONResponse:
    return error_response(request_id, 500, "internal_error", "An unexpected error occurred")


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _format_validation_error(error: dict[str, Any]) -> dict[str, str]:
    loc = list(error.get("loc", ()))
    if loc and loc[0] in _LOC_PREFIXES:
        loc = loc[1:]
    if loc and loc[0] in _UNION_TAGS:
        loc = loc[1:]
    message = str(error.get("msg", "invalid value")).removeprefix("Value error, ")
    return {"field": ".".join(str(part) for part in loc), "message": message}


async def _handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    return error_response(_request_id(request), exc.status_code, exc.code, exc.message)


async def _handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    # A body that isn't JSON at all is a malformed request (400), not a semantic validation failure.
    if any(error.get("type") == "json_invalid" for error in exc.errors()):
        return error_response(_request_id(request), 400, "invalid_json", "Request body is not valid JSON")

    details = [_format_validation_error(error) for error in exc.errors()]
    first = details[0] if details else {"field": "", "message": "Invalid request"}
    message = f"{first['field']}: {first['message']}" if first["field"] else first["message"]
    return error_response(_request_id(request), 422, "validation_error", message, details)


async def _handle_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return error_response(_request_id(request), exc.status_code, "http_error", str(exc.detail))


def register_exception_handlers(app: FastAPI) -> None:
    # Unhandled exceptions are turned into a 500 by RequestContextMiddleware.
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_error)
