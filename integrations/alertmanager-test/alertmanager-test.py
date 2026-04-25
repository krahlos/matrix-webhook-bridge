#!/usr/bin/env python3
"""Nightly smoke test: fires a test alert through Alertmanager and verifies
matrix-webhook-bridge received it.
"""

import json
import logging
import os
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta

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
        tz = time.strftime("%z", ct)
        ts = f"{time.strftime('%Y-%m-%dT%H:%M:%S', ct)}.{int(record.msecs):03d}{tz}"
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


_handler = logging.StreamHandler()
_handler.setFormatter(_JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[_handler])
logger = logging.getLogger("alertmanager-test")

ALERTMANAGER_URL = os.environ.get("ALERTMANAGER_URL", "http://localhost:9093")
MATRIX_WEBHOOK_BRIDGE_URL = os.environ.get("MATRIX_WEBHOOK_BRIDGE_URL", "http://localhost:5001")
WAIT_SECONDS = int(os.environ.get("WAIT_SECONDS", "20"))

_TEST_LABELS = {
    "alertname": "SmokeTest",
    "severity": "critical",
    "service": "alertmanager-test",
}


def _post(url: str, payload: list | dict) -> None:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    urllib.request.urlopen(req, timeout=10)  # nosec B310  # URL sourced from config


def _read_metric(name: str, labels: dict[str, str]) -> float:
    """Return a single counter value from the bridge /metrics endpoint, or 0 on failure."""
    try:
        with urllib.request.urlopen(  # nosec B310  # URL sourced from config
            f"{MATRIX_WEBHOOK_BRIDGE_URL}/metrics", timeout=10
        ) as resp:
            for line in resp.read().decode().splitlines():
                if line.startswith(name) and all(f'{k}="{v}"' in line for k, v in labels.items()):
                    return float(line.rsplit(" ", 1)[-1])
    except Exception as exc:
        logger.warning("Could not read bridge metrics: %s", exc)
    return 0.0


def fire_alert() -> None:
    payload = [
        {
            "labels": _TEST_LABELS,
            "annotations": {
                "summary": "Alertmanager smoke test",
                "description": "Nightly connectivity check — safe to ignore.",
            },
        }
    ]
    _post(f"{ALERTMANAGER_URL}/api/v2/alerts", payload)
    logger.info("Test alert fired.")


def resolve_alert() -> None:
    ends_at = (datetime.now(UTC) - timedelta(seconds=60)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    payload = [{"labels": _TEST_LABELS, "endsAt": ends_at}]
    _post(f"{ALERTMANAGER_URL}/api/v2/alerts", payload)
    logger.info("Test alert resolved.")


def main() -> None:
    before = _read_metric("bridge_notify_success_total", {"service": "alertmanager"})
    logger.info("bridge_notify_success_total before: %s", before)

    fire_alert()

    logger.info("Waiting %s seconds for Alertmanager to fire webhook...", WAIT_SECONDS)
    time.sleep(WAIT_SECONDS)

    resolve_alert()

    after = _read_metric("bridge_notify_success_total", {"service": "alertmanager"})
    logger.info("bridge_notify_success_total after: %s", after)

    if after > before:
        logger.info("Smoke test passed: matrix-webhook-bridge received the alert.")
    else:
        logger.error(
            "Smoke test failed: matrix-webhook-bridge metric did not increase "
            "(before=%s after=%s). Check Alertmanager routing and bridge connectivity.",
            before,
            after,
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()
