from dataclasses import dataclass


@dataclass
class Config:
    base_url: str
    room_id: str
    domain: str
    port: int = 5001
    default_user: str = "bridge"
