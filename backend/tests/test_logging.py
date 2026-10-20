import json
import logging

from app.logging_config import JsonFormatter, RequestIdFilter
from app.request_context import request_id_var


def _record(**extra: object) -> logging.LogRecord:
    record = logging.makeLogRecord({"name": "test", "levelname": "INFO", "msg": "item.ingested"})
    record.__dict__.update(extra)
    return record


def test_filter_adds_current_request_id() -> None:
    token = request_id_var.set("req-7")
    try:
        record = _record()
        RequestIdFilter().filter(record)
    finally:
        request_id_var.reset(token)

    assert record.request_id == "req-7"


def test_filter_leaves_records_outside_requests_untouched() -> None:
    record = _record()
    RequestIdFilter().filter(record)

    assert not hasattr(record, "request_id")


def test_formatter_emits_json_with_extra_fields() -> None:
    line = JsonFormatter().format(_record(item_id=3))

    payload = json.loads(line)
    assert payload["message"] == "item.ingested"
    assert payload["item_id"] == 3
