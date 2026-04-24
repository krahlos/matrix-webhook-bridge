"""Tests for resolve_rooms helper and multi-room routing in /notify."""

from contextlib import contextmanager
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

from matrix_webhook_bridge.config import Config
from matrix_webhook_bridge.server import (
    _get_config,
    _pre_flight_check,
    app,
    resolve_rooms,
)


def _make_config(**kwargs) -> Config:
    defaults = {
        "base_url": "https://matrix.example.com",
        "room_id": "!default:example.com",
        "domain": "example.com",
    }
    defaults.update(kwargs)
    return Config(**defaults)


@contextmanager
def _make_client(config):
    app.dependency_overrides[_get_config] = lambda: config
    app.state.config = config
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def _mock_tokens(tmp_path, monkeypatch):
    monkeypatch.setattr("matrix_webhook_bridge.matrix._TOKENS_DIR", str(tmp_path))
    monkeypatch.setattr("matrix_webhook_bridge.server._TOKENS_DIR", str(tmp_path))
    (tmp_path / "bridge_as_token.txt").write_text("fake-as-token")


class TestResolveRooms:
    def test_room_param_wins_over_service_rooms(self):
        config = _make_config(service_rooms={"svc": ["!other:example.com"]})
        assert resolve_rooms("svc", "!override:example.com", config) == ["!override:example.com"]

    def test_room_param_wins_over_global_default(self):
        config = _make_config()
        assert resolve_rooms(None, "!override:example.com", config) == ["!override:example.com"]

    def test_service_rooms_used_when_no_room_param(self):
        config = _make_config(service_rooms={"svc": ["!a:example.com", "!b:example.com"]})
        assert resolve_rooms("svc", None, config) == ["!a:example.com", "!b:example.com"]

    def test_unknown_service_falls_back_to_global(self):
        config = _make_config(service_rooms={"svc": ["!a:example.com"]})
        assert resolve_rooms("other", None, config) == ["!default:example.com"]

    def test_no_service_falls_back_to_global(self):
        config = _make_config()
        assert resolve_rooms(None, None, config) == ["!default:example.com"]

    def test_no_service_rooms_configured_falls_back_to_global(self):
        config = _make_config()
        assert resolve_rooms("svc", None, config) == ["!default:example.com"]


@pytest.mark.usefixtures("_mock_tokens")
class TestNotifyMultiRoom:
    def test_room_param_routes_to_specified_room(self):
        config = _make_config()
        with patch("matrix_webhook_bridge.server._matrix_notify") as mock_notify:
            with _make_client(config) as client:
                resp = client.post("/notify?room=!custom:example.com", json={"body": "hello"})
        assert resp.status_code == 200
        assert mock_notify.call_count == 1
        assert mock_notify.call_args.args[1] == "!custom:example.com"

    def test_service_rooms_sends_to_all_rooms(self):
        config = _make_config(service_rooms={"svc": ["!room1:example.com", "!room2:example.com"]})
        with patch("matrix_webhook_bridge.server._matrix_notify") as mock_notify:
            with _make_client(config) as client:
                resp = client.post("/notify?service=svc", json={"body": "hello"})
        assert resp.status_code == 200
        assert mock_notify.call_count == 2
        called_rooms = [c.args[1] for c in mock_notify.call_args_list]
        assert called_rooms == ["!room1:example.com", "!room2:example.com"]

    def test_room_param_overrides_service_rooms(self):
        config = _make_config(service_rooms={"svc": ["!room1:example.com"]})
        with patch("matrix_webhook_bridge.server._matrix_notify") as mock_notify:
            with _make_client(config) as client:
                resp = client.post(
                    "/notify?service=svc&room=!override:example.com", json={"body": "hello"}
                )
        assert resp.status_code == 200
        assert mock_notify.call_count == 1
        assert mock_notify.call_args.args[1] == "!override:example.com"

    def test_no_service_rooms_uses_global_default(self):
        config = _make_config()
        with patch("matrix_webhook_bridge.server._matrix_notify") as mock_notify:
            with _make_client(config) as client:
                resp = client.post("/notify", json={"body": "hello"})
        assert resp.status_code == 200
        assert mock_notify.call_count == 1
        assert mock_notify.call_args.args[1] == "!default:example.com"


class TestPreFlightServiceRooms:
    @pytest.fixture
    def tokens_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr("matrix_webhook_bridge.matrix._TOKENS_DIR", str(tmp_path))
        monkeypatch.setattr("matrix_webhook_bridge.server._TOKENS_DIR", str(tmp_path))
        (tmp_path / "bridge_as_token.txt").write_text("tok")
        return tmp_path

    def test_accepts_valid_service_rooms(self, tokens_dir):
        config = _make_config(service_rooms={"svc": ["!room1:example.com", "!room2:example.com"]})
        _pre_flight_check(config)

    def test_rejects_invalid_room_id_format(self, tokens_dir):
        config = _make_config(service_rooms={"svc": ["not-a-room-id"]})
        with pytest.raises(RuntimeError, match="Invalid room_id"):
            _pre_flight_check(config)

    def test_rejects_room_id_without_exclamation(self, tokens_dir):
        config = _make_config(service_rooms={"svc": ["room:example.com"]})
        with pytest.raises(RuntimeError, match="Invalid room_id"):
            _pre_flight_check(config)
