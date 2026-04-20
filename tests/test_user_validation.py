"""Tests for user parameter validation to prevent path traversal."""

import pytest

from matrix_webhook_bridge.config import Config
from matrix_webhook_bridge.server import _pre_flight_check, _validate_user_localpart


class _FakeHandler:
    """Minimal mock HTTP handler for testing validation."""

    def __init__(self):
        self.client_address = ("127.0.0.1", 12345)
        self.response_code = None
        self.headers_sent = []
        self.response_body = b""

    def send_response(self, code: int) -> None:
        self.response_code = code

    def send_header(self, key: str, value: str) -> None:
        self.headers_sent.append((key, value))

    def end_headers(self) -> None:
        pass

    class wfile:
        @staticmethod
        def write(data: bytes) -> None:
            pass


@pytest.mark.parametrize(
    "user",
    [
        "bridge",
        "alertmanager",
        "crowdsec",
        "borgmatic",
        "user123",
        "my-user",
        "my_user",
        "my.user",
        "a",
        "user-with-many-parts",
        "user_123.test-name",
    ],
)
def test_validate_user_localpart_accepts_valid_users(user):
    """Valid Matrix localparts should pass validation."""
    handler = _FakeHandler()
    assert _validate_user_localpart(user, handler) is True
    assert handler.response_code is None


@pytest.mark.parametrize(
    "user",
    [
        "../secret",
        "../../etc/passwd",
        "/etc/passwd",
        "../",
        "./",
        "user/path",
        "user\\path",
        "user with spaces",
        "UPPERCASE",
        "User",
        "user@domain",
        "user:domain",
        "user;cmd",
        "user|cmd",
        "user&cmd",
        "user$var",
        "user`cmd`",
        "user'cmd'",
        'user"cmd"',
        "user<cmd>",
        "user{cmd}",
        "user[cmd]",
        "",
    ],
)
def test_validate_user_localpart_rejects_invalid_users(user):
    """Invalid or malicious user parameters should be rejected."""
    handler = _FakeHandler()
    assert _validate_user_localpart(user, handler) is False
    assert handler.response_code == 400


@pytest.fixture
def secrets_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("matrix_webhook_bridge.matrix._SECRETS_DIR", str(tmp_path))
    monkeypatch.setattr("matrix_webhook_bridge.server._SECRETS_DIR", str(tmp_path))
    return tmp_path


def test_pre_flight_check_validates_default_user(secrets_dir):
    """Pre-flight check should reject invalid default_user to prevent path traversal."""
    (secrets_dir / "../secret_as_token.txt").write_text("tok")

    config = Config(
        base_url="https://matrix.example.com",
        room_id="!room:example.com",
        domain="example.com",
        default_user="../secret",
    )

    with pytest.raises(RuntimeError, match="Invalid default_user"):
        _pre_flight_check(config)


def test_pre_flight_check_accepts_valid_default_user(secrets_dir):
    """Pre-flight check should accept valid default_user."""
    (secrets_dir / "bridge_as_token.txt").write_text("tok")

    config = Config(
        base_url="https://matrix.example.com",
        room_id="!room:example.com",
        domain="example.com",
        default_user="bridge",
    )

    # Should not raise
    _pre_flight_check(config)
