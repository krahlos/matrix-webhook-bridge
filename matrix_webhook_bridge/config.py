from dataclasses import dataclass, field


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
