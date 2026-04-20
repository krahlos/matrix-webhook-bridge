from dataclasses import dataclass


@dataclass
class Config:
    base_url: str
    room_id: str
    domain: str
    port: int = 5001
    default_user: str = "bridge"
    matrix_timeout: int = 5
    webhook_secret: str | None = None
