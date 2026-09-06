from dataclasses import dataclass, field

# Shared with config_loader.py's CONFIG_SCHEMA so the YAML-load-time check and
# server.py's pre-flight check can't drift apart.
LOCALPART_PATTERN = r"^[a-z0-9._\-]+$"
ROOM_ID_PATTERN = r"^![^:]+:.+$"


@dataclass
class Config:
    base_url: str
    room_id: str
    domain: str
    port: int = 5001
    default_user: str = "bridge"
    matrix_timeout: int = 5
    webhook_secret: str | None = None
    service_users: dict[str, str] = field(default_factory=dict)
    service_rooms: dict[str, list[str]] = field(default_factory=dict)
    autojoin: bool = False
