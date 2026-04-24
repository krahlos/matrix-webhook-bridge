import logging

import pytest

from matrix_webhook_bridge.config import Config
from matrix_webhook_bridge.server import _pre_flight_check


@pytest.fixture
def tokens_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("matrix_webhook_bridge.matrix._TOKENS_DIR", str(tmp_path))
    monkeypatch.setattr("matrix_webhook_bridge.server._TOKENS_DIR", str(tmp_path))
    return tmp_path


def _make_config(default_user: str = "bridge") -> Config:
    return Config(
        base_url="https://matrix.example.com",
        room_id="!room:example.com",
        domain="example.com",
        default_user=default_user,
    )


def test_raises_when_default_user_token_missing(tokens_dir):
    with pytest.raises(RuntimeError, match="bridge"):
        _pre_flight_check(_make_config())


def test_passes_when_default_user_token_present(tokens_dir):
    (tokens_dir / "bridge_as_token.txt").write_text("tok")
    _pre_flight_check(_make_config())


def test_uses_configured_default_user(tokens_dir):
    (tokens_dir / "custom_as_token.txt").write_text("tok")
    _pre_flight_check(_make_config(default_user="custom"))


def test_raises_for_custom_default_user_without_token(tokens_dir):
    (tokens_dir / "bridge_as_token.txt").write_text("tok")
    with pytest.raises(RuntimeError, match="custom"):
        _pre_flight_check(_make_config(default_user="custom"))


def test_warns_on_misnamed_secret_file(tokens_dir, caplog):
    (tokens_dir / "bridge_as_token.txt").write_text("tok")
    (tokens_dir / "unexpected.txt").write_text("x")
    with caplog.at_level(logging.WARNING, logger="matrix_webhook_bridge.server"):
        _pre_flight_check(_make_config())
    assert any("unexpected.txt" in r.getMessage() for r in caplog.records)
