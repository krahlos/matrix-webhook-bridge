"""Tests for _autojoin_all startup behaviour."""

import logging
from unittest.mock import ANY, patch

from matrix_webhook_bridge.config import Config
from matrix_webhook_bridge.server import _autojoin_all


def _cfg(**kwargs) -> Config:
    defaults = {
        "base_url": "https://matrix.example.com",
        "room_id": "!default:example.com",
        "domain": "example.com",
    }
    defaults.update(kwargs)
    return Config(**defaults)


class TestAutojoinAll:
    def test_joins_default_user_to_global_room(self):
        config = _cfg()
        with patch("matrix_webhook_bridge.server._join_room") as mock_join:
            _autojoin_all(config)
        mock_join.assert_called_once_with(
            "https://matrix.example.com",
            "!default:example.com",
            ANY,
            "@bridge:example.com",
            5,
        )

    def test_service_user_joins_service_rooms(self):
        config = _cfg(
            service_users={"svc": "svcbot"},
            service_rooms={"svc": ["!room1:example.com", "!room2:example.com"]},
        )
        with patch("matrix_webhook_bridge.server._join_room") as mock_join:
            _autojoin_all(config)
        called = [(c.args[3], c.args[1]) for c in mock_join.call_args_list]
        assert ("@svcbot:example.com", "!room1:example.com") in called
        assert ("@svcbot:example.com", "!room2:example.com") in called

    def test_service_without_user_uses_default_user(self):
        config = _cfg(service_rooms={"svc": ["!svcroom:example.com"]})
        with patch("matrix_webhook_bridge.server._join_room") as mock_join:
            _autojoin_all(config)
        called = [(c.args[3], c.args[1]) for c in mock_join.call_args_list]
        assert ("@bridge:example.com", "!svcroom:example.com") in called

    def test_join_failure_is_logged_and_does_not_raise(self, caplog):
        config = _cfg()
        with patch(
            "matrix_webhook_bridge.server._join_room", side_effect=Exception("network error")
        ):
            with caplog.at_level(logging.ERROR):
                _autojoin_all(config)  # must not raise
        assert any("autojoin failed" in r.getMessage() for r in caplog.records)

    def test_service_user_without_service_rooms_joins_default_room(self):
        config = _cfg(service_users={"diun": "diun"})
        with patch("matrix_webhook_bridge.server._join_room") as mock_join:
            _autojoin_all(config)
        called = [(c.args[3], c.args[1]) for c in mock_join.call_args_list]
        assert ("@diun:example.com", "!default:example.com") in called

    def test_autojoin_false_skipped_at_lifespan(self):
        config = _cfg(autojoin=False)
        assert not config.autojoin
