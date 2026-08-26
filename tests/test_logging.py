import json
import logging

from app.core.logging import JsonFormatter, request_id_context


def test_json_formatter_adds_request_and_operational_fields() -> None:
    record = logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="request_completed",
        args=(),
        exc_info=None,
    )
    record.http_method = "GET"  # type: ignore[attr-defined]
    record.status_code = 200  # type: ignore[attr-defined]
    token = request_id_context.set("trace-123")

    try:
        output = json.loads(JsonFormatter().format(record))
    finally:
        request_id_context.reset(token)

    assert output["event"] == "request_completed"
    assert output["level"] == "INFO"
    assert output["request_id"] == "trace-123"
    assert output["http_method"] == "GET"
    assert output["status_code"] == 200
    assert output["timestamp"].endswith("+00:00")
