#!/usr/bin/env python3
"""Sends a daily summary of CrowdSec blocks via matrix-webhook-bridge."""

import json
import logging
import os
import subprocess  # nosec B404  # intentional, used for docker exec
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict

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
logger = logging.getLogger("crowdsec-summary")

MATRIX_WEBHOOK_BRIDGE_URL = os.environ.get("MATRIX_WEBHOOK_BRIDGE_URL", "http://localhost:5001")
SINCE = os.environ.get("SINCE", "24h")
TOP_TARGETS = int(os.environ.get("TOP_TARGETS", "5"))
TOP_COUNTRIES = int(os.environ.get("TOP_COUNTRIES", "5"))
TOP_OFFENDERS = int(os.environ.get("TOP_OFFENDERS", "3"))


def _run_cscli(*args: str) -> list:
    result = subprocess.run(  # nosec B603 B607  # hardcoded docker exec, no user input
        ["docker", "exec", "crowdsec", "cscli", *args, "-o", "json"],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout) or []


def fetch_alerts_since() -> list:
    return _run_cscli("alerts", "list", "--since", SINCE, "--limit", "0")


def fetch_active_decisions() -> list:
    return _run_cscli("decisions", "list", "--limit", "0")


def _event_meta(alert: dict) -> dict[str, str]:
    events = alert.get("events", [])
    if not events:
        return {}
    return {m["key"]: m["value"] for m in events[0].get("meta", [])}


def _target(alert: dict) -> str:
    meta = _event_meta(alert)
    service = meta.get("service", "")
    fqdn = meta.get("target_fqdn", "")
    if service and fqdn:
        return f"{service}://{fqdn}"
    return fqdn or service or "other"


def _flag(cc: str) -> str:
    if not cc or len(cc) != 2 or not cc.isalpha():
        return ""
    base = 0x1F1E6 - ord("A")
    return chr(base + ord(cc.upper()[0])) + chr(base + ord(cc.upper()[1]))


def _short_scenario(scenario: str) -> str:
    """Strip vendor prefix (e.g. crowdsecurity/) for display."""
    return scenario.split("/", 1)[-1] if "/" in scenario else scenario


def build_payload(alerts: list, active_count: int) -> dict:
    total_bans = 0
    unique_ips: set = set()
    country_counter: Counter = Counter()
    target_bans: Counter = Counter()
    target_scenarios: dict[str, set] = defaultdict(set)
    offender_counter: Counter = Counter()
    offender_meta: dict[str, str] = {}

    for alert in alerts:
        source = alert.get("source", {})
        ip = source.get("value", "?")
        cn = source.get("cn", "") or "?"
        as_number = source.get("as_number", "")
        as_name = source.get("as_name", "")
        scenario = _short_scenario(alert.get("scenario", "?"))
        target = _target(alert)

        decisions = alert.get("decisions", [])
        ban_count = len(decisions)
        total_bans += ban_count
        unique_ips.add(ip)
        if cn != "?":
            country_counter[cn] += ban_count
        target_bans[target] += ban_count
        target_scenarios[target].add(scenario)
        offender_counter[ip] += ban_count
        as_info = f"AS{as_number} {as_name}".strip() if as_number or as_name else ""
        offender_meta[ip] = f"{cn}" + (f" · {as_info}" if as_info else "")

    if total_bans == 0:
        return {}

    date_str = time.strftime("%-d %b %Y")
    scenario_count = len({s for scenarios in target_scenarios.values() for s in scenarios})

    top = target_bans.most_common(TOP_TARGETS)
    shown = sum(c for _, c in top)
    other = total_bans - shown
    top_countries = country_counter.most_common(TOP_COUNTRIES)
    country_str = " · ".join(f"{_flag(cc)}{cc} {n}" for cc, n in top_countries)

    def _display_target(tgt: str) -> str:
        """Strip scheme for brevity."""
        for prefix in ("https://", "http://"):
            if tgt.startswith(prefix):
                return tgt[len(prefix) :]
        return tgt

    # --- plain text ---
    lines = [
        f"🛡️ CrowdSec Daily Summary — {date_str}",
        f"{total_bans} bans · {len(unique_ips)} IPs · {scenario_count} scenarios",
        "",
        "By target:",
    ]
    for tgt, count in top:
        lines.append(f"{_display_target(tgt)} — {count} bans")
        for s in sorted(target_scenarios[tgt]):
            lines.append(f"• {s}")
    if other > 0:
        lines.append(f"+ {other} more")

    lines += ["", "Countries:", country_str, ""]
    lines.append("Top offenders:")
    for ip, count in offender_counter.most_common(TOP_OFFENDERS):
        lines.append(f"{ip} — {count} bans")
        lines.append(f"• {offender_meta[ip]}")

    lines += ["", f"Active bans: {active_count}"]
    plain = "\n".join(lines)

    # --- html ---
    def h(s: str) -> str:
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    html_lines = [
        f"<b>🛡️ CrowdSec Daily Summary — {h(date_str)}</b><br>",
        f"{total_bans} bans · {len(unique_ips)} IPs · {scenario_count} scenarios",
        "<br><br><b>By target:</b><br>",
    ]
    for tgt, count in top:
        html_lines.append(f"<b>{h(_display_target(tgt))}</b> — {count} bans<br>")
        for s in sorted(target_scenarios[tgt]):
            html_lines.append(f"&nbsp;&nbsp;• {h(s)}<br>")
    if other > 0:
        html_lines.append(f"+ {other} more</i><br>")

    html_lines.append(f"<br><b>Countries:</b><br>{h(country_str)}<br>")

    html_lines.append("<br><b>Top offenders:</b><br>")
    for ip, count in offender_counter.most_common(TOP_OFFENDERS):
        html_lines.append(f"<b>{h(ip)}</b> — {count} bans<br>")
        html_lines.append(f"&nbsp;&nbsp;• {h(offender_meta[ip])}<br>")

    html_lines.append(f"<br><b>Active bans:</b> {active_count}")
    html = "".join(html_lines)

    return {"body": plain, "html": html}


def send(payload: dict) -> None:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{MATRIX_WEBHOOK_BRIDGE_URL}/notify?service=crowdsec",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=30)  # nosec B310  # URL sourced from config
    except (urllib.error.URLError, OSError) as e:
        logger.error("Failed to send digest via matrix-webhook-bridge: %s", e)


def main() -> None:
    alerts = fetch_alerts_since()
    if not alerts:
        logger.info("No alerts in the last %s — skipping summary.", SINCE)
        return

    active = fetch_active_decisions()
    active_count = len(active)

    payload = build_payload(alerts, active_count)
    if not payload:
        logger.info("No bans found in digest window — skipping.")
        return

    ban_count = sum(len(a.get("decisions", [])) for a in alerts)
    logger.info("Sending digest: %s bans, %s active.", ban_count, active_count)
    send(payload)
    logger.info("Done.")


if __name__ == "__main__":
    main()
