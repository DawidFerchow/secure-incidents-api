from __future__ import annotations

import json
import logging
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)

_EXTRA_FIELDS = (
    "http_method",
    "path",
    "status_code",
    "duration_ms",
    "incident_id",
    "record_count",
    "seed_records",
)


class JsonFormatter(logging.Formatter):
    """Render one JSON object per line for machine-friendly ingestion."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }

        request_id = request_id_context.get()
        if request_id:
            payload["request_id"] = request_id

        for field in _EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)

    # Uvicorn access logs would duplicate the structured request middleware logs.
    logging.getLogger("uvicorn.access").disabled = True
