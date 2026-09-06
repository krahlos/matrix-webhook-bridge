"""Formatter for Grafana's webhook notifier.

Payload schema: https://grafana.com/docs/grafana/latest/alerting/configure-notifications/manage-contact-points/integrations/webhook-notifier/
"""

from html import escape


def format_grafana(data: dict) -> list[tuple[str, str]]:
    """Format a Grafana unified alerting webhook payload to a Matrix message."""
    out = []
    for a in data.get("alerts", []):
        name = a.get("labels", {}).get("alertname", "?")
        severity = a.get("labels", {}).get("severity", "").upper()
        summary = a.get("annotations", {}).get("summary", name)
        desc = a.get("annotations", {}).get("description", "")
        starts_at = a.get("startsAt", "")
        link = a.get("dashboardURL") or a.get("panelURL") or a.get("generatorURL", "")
        firing = a.get("status") == "firing"
        icon, color = ("🔥", "#e74c3c") if firing else ("✅", "#2ecc71")

        plain = f"{icon} [{severity}] {summary}" if severity else f"{icon} {summary}"
        if starts_at:
            plain += f" (since {starts_at})"

        escaped_severity = escape(severity)
        escaped_summary = escape(summary)
        escaped_desc = escape(desc)
        escaped_starts_at = escape(starts_at)
        escaped_href = escape(link, quote=True)

        label = f"[{escaped_severity}] {escaped_summary}" if severity else escaped_summary
        html = f'<b><font color="{color}">{icon} {label}</font></b>'
        if desc:
            html += f"<br/><i>{escaped_desc}</i>"
        if starts_at:
            html += f"<br/>Since: {escaped_starts_at}"
        if link:
            html += f'<br/><a href="{escaped_href}">View in Grafana</a>'
        out.append((plain, html))
    return out
