"""Tests for user localpart validation in pre-flight checks."""

import pytest

from matrix_webhook_bridge.config import Config
from matrix_webhook_bridge.server import _pre_flight_check


@pytest.fixture
def tokens_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("matrix_webhook_bridge.matrix._TOKENS_DIR", str(tmp_path))
    monkeypatch.setattr("matrix_webhook_bridge.server._TOKENS_DIR", str(tmp_path))
    return tmp_path


def _base_config(**kwargs) -> Config:
    return Config(
        base_url="https://matrix.example.com",
        room_id="!room:example.com",
        domain="example.com",
        **kwargs,
    )


def test_pre_flight_check_validates_default_user(tokens_dir):
    """Pre-flight check should reject invalid default_user to prevent path traversal."""
    config = _base_config(default_user="../secret")
    with pytest.raises(RuntimeError, match="Invalid default_user"):
        _pre_flight_check(config)


def test_pre_flight_check_accepts_valid_default_user(tokens_dir):
    """Pre-flight check should accept valid default_user."""
    (tokens_dir / "bridge_as_token.txt").write_text("tok")
    config = _base_config(default_user="bridge")
    _pre_flight_check(config)


@pytest.mark.parametrize(
    "user",
    [
        "../secret",
        "../../etc/passwd",
        "/etc/passwd",
        "user/path",
        "user with spaces",
        "UPPERCASE",
        "user@domain",
    ],
)
def test_pre_flight_rejects_invalid_service_user(tokens_dir, user):
    """Pre-flight check should reject invalid service_users localparts."""
    (tokens_dir / "bridge_as_token.txt").write_text("tok")
    config = _base_config(service_users={"mysvc": user})
    with pytest.raises(RuntimeError, match="Invalid user"):
        _pre_flight_check(config)


@pytest.mark.parametrize(
    "user",
    [
        "alertmanager",
        "borgmatic",
        "crowdsec",
        "my-bot",
        "my_bot",
        "my.bot",
        "bot123",
    ],
)
def test_pre_flight_accepts_valid_service_users(tokens_dir, user):
    """Pre-flight check should accept valid service_users localparts."""
    (tokens_dir / "bridge_as_token.txt").write_text("tok")
    config = _base_config(service_users={"mysvc": user})
    _pre_flight_check(config)
