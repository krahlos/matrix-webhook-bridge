#!/usr/bin/env python3
"""Reports new CrowdSec decisions via matrix-webhook-bridge."""

import json
import logging
import os
import subprocess  # nosec B404  # intentional, used for docker exec
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
logger = logging.getLogger("crowdsec-notifications")

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
SINCE = os.environ.get("SINCE", "5m")


def fetch_decisions() -> list:
    result = subprocess.run(  # nosec B603 B607  # hardcoded docker exec, no user input
        [
            "docker",
            "exec",
            "crowdsec",
            "cscli",
            "decisions",
            "list",
            "--since",
            SINCE,
            "-o",
            "json",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout) or []


def _event_meta(alert: dict) -> dict[str, str]:
    events = alert.get("events", [])
    if not events:
        return {}
    return {m["key"]: m["value"] for m in events[0].get("meta", [])}


def build_payloads(data: list) -> list[dict]:
    payloads = []
    for alert in data:
        scenario = alert.get("scenario", "?")
        source = alert.get("source", {})
        ip = source.get("value", "?")
        cn = source.get("cn", "?")
        as_name = source.get("as_name", "")
        as_number = source.get("as_number", "")
        events_count = alert.get("events_count", "?")
        as_info = f"AS{as_number} {as_name}".strip() if as_number or as_name else "?"

        meta = _event_meta(alert)
        service = meta.get("service", "")
        fqdn = meta.get("target_fqdn", "")
        target = f"{service}://{fqdn}" if service and fqdn else fqdn or service or "?"

        for decision in alert.get("decisions", []):
            value = decision.get("value", ip)
            duration = decision.get("duration", "?")
            dec_type = decision.get("type", "ban")

            plain = (
                f"🚫 CrowdSec {dec_type}: {value}\n"
                f"Scenario: {scenario} ({events_count} events)\n"
                f"Target: {target}\n"
                f"Country: {cn} | AS: {as_info}\n"
                f"Duration: {duration}"
            )
            html = (
                f"<b>🚫 CrowdSec {dec_type}:</b> <code>{value}</code><br>"
                f"<b>Scenario:</b> {scenario} ({events_count} events)<br>"
                f"<b>Target:</b> {target}<br>"
                f"<b>Country:</b> {cn} | <b>AS:</b> {as_info}<br>"
                f"<b>Duration:</b> {duration}"
            )
            payloads.append({"body": plain, "html": html})

    return payloads


def send(payload: dict) -> None:
    data = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    if WEBHOOK_SECRET:
        headers["Authorization"] = f"Bearer {WEBHOOK_SECRET}"
    req = urllib.request.Request(
        f"{MATRIX_WEBHOOK_BRIDGE_URL}/notify?service=crowdsec",
        data=data,
        headers=headers,
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=5)  # nosec B310  # URL sourced from config
    except urllib.error.URLError as e:
        logger.error("Failed to send notification via matrix-webhook-bridge: %s", e)


def main() -> None:
    decisions = fetch_decisions()
    if not decisions:
        logger.info("No new decisions in the last %s.", SINCE)
        return
    payloads = build_payloads(decisions)
    logger.info("Sending %d notification(s) for %d decision(s).", len(payloads), len(decisions))
    for i, payload in enumerate(payloads):
        if i > 0:
            time.sleep(1)
        send(payload)
    logger.info("Done.")


if __name__ == "__main__":
    main()
