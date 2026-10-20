"""Per-request context shared with code that has no access to the Request object (e.g. logging)."""

from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
