"""A small in-memory ring of recent WARNING/ERROR log lines for the admin monitoring page.

It is process-local and lost on restart; the page says so. Only the logger name, level, time and
the formatted message (truncated) are kept: never extra fields, request bodies or exception text.
"""

import logging
import re
from collections import deque
from datetime import UTC, datetime
from typing import Any

STARTED_AT = datetime.now(UTC)
_CAPACITY = 100
_events: deque[dict[str, Any]] = deque(maxlen=_CAPACITY)
_SECRETISH = re.compile(
    r"(?i)(bearer\s+\S+|secret\S*\s*[=:]\s*\S+|key\S*\s*[=:]\s*\S+|token\S*\s*[=:]\s*\S+)"
)


class RingHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        if record.levelno < logging.WARNING:
            return
        try:
            message = _SECRETISH.sub("[redacted]", record.getMessage())[:300]
        except Exception:  # never let monitoring break logging
            message = "(unprintable log message)"
        _events.append(
            {
                "at": datetime.fromtimestamp(record.created, UTC),
                "level": record.levelname,
                "logger": record.name,
                "message": message,
            }
        )


def install() -> None:
    root = logging.getLogger()
    if not any(isinstance(h, RingHandler) for h in root.handlers):
        root.addHandler(RingHandler(level=logging.WARNING))


def recent(limit: int = 50) -> list[dict[str, Any]]:
    return list(reversed(_events))[:limit]


def counts() -> dict[str, int]:
    out = {"WARNING": 0, "ERROR": 0, "CRITICAL": 0}
    for e in _events:
        out[e["level"]] = out.get(e["level"], 0) + 1
    return out
