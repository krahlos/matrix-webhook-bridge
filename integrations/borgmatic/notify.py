#!/usr/bin/env python3
"""Reports borgmatic backup status via matrix-webhook-bridge."""

import json
import logging
import os
import socket
import sys
import time
import urllib.error
import urllib.request

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
logger = logging.getLogger("borgmatic-notifications")

MATRIX_WEBHOOK_BRIDGE_URL = os.environ.get("MATRIX_WEBHOOK_BRIDGE_URL", "http://localhost:5001")
BRIDGE_CONFIG = os.environ.get("BRIDGE_CONFIG", "")


def _load_webhook_secret() -> str:
    """Read webhook_secret from the bridge config file.

    Falls back to WEBHOOK_SECRET env var if the config file is not set
    or pyyaml is not installed.
    """
    if BRIDGE_CONFIG:
        try:
            import yaml

            with open(BRIDGE_CONFIG) as f:
                data = yaml.safe_load(f)
            secret = data.get("server", {}).get("webhook_secret", "")
            if secret:
                return secret
        except Exception as exc:
            logger.warning("Could not read webhook_secret from %s: %s", BRIDGE_CONFIG, exc)
    return os.environ.get("WEBHOOK_SECRET", "")


WEBHOOK_SECRET = _load_webhook_secret()


def build_payload(status: str) -> dict:
    hostname = socket.gethostname().split(".")[0]
    if status == "success":
        body = f"✅ Backup completed successfully on `{hostname}`"
        html = f"<b>✅ Backup completed successfully</b> on <code>{hostname}</code>"
    else:
        body = f"💥 Backup failed on `{hostname}`"
        html = f"<b>💥 Backup failed</b> on <code>{hostname}</code>"
    return {"body": body, "html": html}


def send(payload: dict) -> None:
    data = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    if WEBHOOK_SECRET:
        headers["Authorization"] = f"Bearer {WEBHOOK_SECRET}"
    req = urllib.request.Request(
        f"{MATRIX_WEBHOOK_BRIDGE_URL}/notify?service=borgmatic",
        data=data,
        headers=headers,
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=5)  # nosec B310  # URL sourced from config
    except urllib.error.URLError as e:
        logger.error("Failed to send notification via matrix-webhook-bridge: %s", e)


def main() -> None:
    status = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    payload = build_payload(status)
    logger.info("Sending borgmatic %s notification.", status)
    send(payload)
    logger.info("Done.")


if __name__ == "__main__":
    main()
