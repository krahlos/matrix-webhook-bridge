import json
import logging
import os
import time
from contextvars import ContextVar

request_id: ContextVar[str] = ContextVar("request_id", default="")

_STDLIB_ATTRS = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "taskName",
        "message",
    }
)


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        ct = time.localtime(record.created)
        ts = f"{time.strftime('%Y-%m-%dT%H:%M:%S', ct)}.{int(record.msecs):03d}{time.strftime('%z', ct)}"  # noqa: E501
        entry: dict = {
            "ts": ts,
            "level": record.levelname.lower(),
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        extra = {
            k: v
            for k, v in record.__dict__.items()
            if k not in _STDLIB_ATTRS and not k.startswith("_")
        }
        if extra:
            entry.update(extra)
        return json.dumps(entry, default=str)


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        rid = request_id.get()
        if rid:
            record.request_id = rid
        return True


def setup_logging() -> None:
    debug = os.environ.get("ENABLE_DEBUG_LOGGING", "0").lower() in ("1", "true")
    log_level = logging.DEBUG if debug else logging.INFO
    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter())
    handler.addFilter(_RequestIdFilter())
    logging.basicConfig(level=log_level, handlers=[handler])
