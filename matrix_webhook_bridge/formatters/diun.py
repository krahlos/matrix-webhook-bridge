def format_diun(data: dict) -> list[tuple[str, str]]:
    """Format a Diun webhook payload to a Matrix message."""
    image = data.get("image", "?")
    status = data.get("status", "")
    hostname = data.get("hostname", "")
    platform = data.get("platform", "")
    hub_link = data.get("hub_link", "")
    created = data.get("created", "")

    icon = "🆕" if status == "new" else "🔄"
    status_label = status.upper() if status else "UPDATE"

    plain = f"{icon} [{status_label}] {image}"
    if hostname:
        plain += f" on {hostname}"
    if platform:
        plain += f" ({platform})"

    if hub_link:
        html = f'{icon} [{status_label}] <a href="{hub_link}">{image}</a>'
    else:
        html = f"{icon} [{status_label}] <b>{image}</b>"
    if hostname:
        html += f" on <i>{hostname}</i>"
    if platform:
        html += f" <code>{platform}</code>"
    if created:
        html += f"<br/>Created: {created}"

    return [(plain, html)]
