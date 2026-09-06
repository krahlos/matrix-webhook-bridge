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

    def test_service_with_empty_room_list_falls_back_to_default_room(self):
        config = _cfg(service_users={"svc": "svcbot"}, service_rooms={"svc": []})
        with patch("matrix_webhook_bridge.server._join_room") as mock_join:
            _autojoin_all(config)
        called = [(c.args[3], c.args[1]) for c in mock_join.call_args_list]
        assert ("@svcbot:example.com", "!default:example.com") in called

    def test_join_failure_falls_back_to_invite_then_retry(self):
        config = _cfg(service_users={"svc": "svcbot"}, service_rooms={"svc": ["!room:example.com"]})

        target_room_attempts = {"n": 0}

        def join_side_effect(base_url, room_id, token_file, user_id, timeout):
            if room_id == "!room:example.com":
                target_room_attempts["n"] += 1
                if target_room_attempts["n"] == 1:
                    raise Exception("not invited")

        with (
            patch(
                "matrix_webhook_bridge.server._join_room", side_effect=join_side_effect
            ) as mock_join,
            patch("matrix_webhook_bridge.server._invite_room") as mock_invite,
        ):
            _autojoin_all(config)
        mock_invite.assert_called_once_with(
            "https://matrix.example.com",
            "!room:example.com",
            ANY,
            "@bridge:example.com",
            "@svcbot:example.com",
            5,
        )
        svcbot_joins = [c for c in mock_join.call_args_list if c.args[3] == "@svcbot:example.com"]
        assert len(svcbot_joins) == 2

    def test_invite_failure_is_logged_distinctly_and_does_not_retry_join(self, caplog):
        config = _cfg(service_users={"svc": "svcbot"}, service_rooms={"svc": ["!room:example.com"]})
        with (
            patch(
                "matrix_webhook_bridge.server._join_room",
                side_effect=Exception("not invited"),
            ) as mock_join,
            patch(
                "matrix_webhook_bridge.server._invite_room",
                side_effect=Exception("insufficient power level"),
            ),
            caplog.at_level(logging.ERROR),
        ):
            _autojoin_all(config)
        assert any("autojoin failed: invite failed" in r.getMessage() for r in caplog.records)
        svcbot_joins = [c for c in mock_join.call_args_list if c.args[3] == "@svcbot:example.com"]
        assert len(svcbot_joins) == 1

    def test_join_after_invite_failure_is_logged_distinctly(self, caplog):
        config = _cfg(service_users={"svc": "svcbot"}, service_rooms={"svc": ["!room:example.com"]})
        with (
            patch(
                "matrix_webhook_bridge.server._join_room",
                side_effect=Exception("not invited"),
            ) as mock_join,
            patch("matrix_webhook_bridge.server._invite_room"),
            caplog.at_level(logging.ERROR),
        ):
            _autojoin_all(config)
        assert any(
            "autojoin failed: join after invite failed" in r.getMessage() for r in caplog.records
        )
        svcbot_joins = [c for c in mock_join.call_args_list if c.args[3] == "@svcbot:example.com"]
        assert len(svcbot_joins) == 2
