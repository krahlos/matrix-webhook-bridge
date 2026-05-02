from html import escape


def format_alertmanager(data: dict) -> list[tuple[str, str]]:
    """Format an Alertmanager webhook payload to a Matrix message."""
    out = []
    external_url = data.get("externalURL", "")
    for a in data.get("alerts", []):
        name = a["labels"].get("alertname", "?")
        severity = a["labels"].get("severity", "").upper()
        summary = a.get("annotations", {}).get("summary", name)
        desc = a.get("annotations", {}).get("description", "")
        starts_at = a.get("startsAt", "")
        fingerprint = a.get("fingerprint", "")
        firing = a["status"] == "firing"
        icon, color = ("🔥", "#e74c3c") if firing else ("✅", "#2ecc71")
        plain = f"{icon} [{severity}] {summary}"
        if starts_at:
            plain += f" (since {starts_at})"

        escaped_severity = escape(severity)
        escaped_summary = escape(summary)
        html = f'<b><font color="{color}">{icon} [{escaped_severity}] {escaped_summary}</font></b>'
        if desc:
            html += f"<br/><i>{escape(desc)}</i>"
        if starts_at:
            html += f"<br/>Since: {escape(starts_at)}"
        if fingerprint and external_url:
            href = escape(f"{external_url}/#/alerts?fingerprint={fingerprint}", quote=True)
            html += f'<br/><a href="{href}">View in Alertmanager</a>'
        out.append((plain, html))
    return out
