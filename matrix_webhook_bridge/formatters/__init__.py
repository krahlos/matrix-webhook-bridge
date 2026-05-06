import json
from typing import Protocol

from .alertmanager import format_alertmanager
from .diun import format_diun


class Formatter(Protocol):
    def __call__(self, data: dict) -> list[tuple[str, str]]: ...


def format_generic(data: dict) -> list[tuple[str, str]]:
    """Format a generic webhook payload to a Matrix message."""
    plain = data.get("body") or json.dumps(data)
    html = data.get("html") or plain
    return [(plain, html)]


SERVICES: dict[str, Formatter] = {
    "alertmanager": format_alertmanager,
    "diun": format_diun,
}
