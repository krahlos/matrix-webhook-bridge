"""Tests for GET /healthy/matrix endpoint."""

from contextlib import contextmanager
from unittest.mock import patch
from urllib.error import URLError

import pytest
from starlette.testclient import TestClient

from matrix_webhook_bridge.config import Config
from matrix_webhook_bridge.server import _get_config, app


@pytest.fixture
def _mock_tokens(tmp_path, monkeypatch):
    monkeypatch.setattr("matrix_webhook_bridge.matrix._TOKENS_DIR", str(tmp_path))
    monkeypatch.setattr("matrix_webhook_bridge.server._TOKENS_DIR", str(tmp_path))
    (tmp_path / "bridge_as_token.txt").write_text("fake-as-token")


def _make_config(**overrides) -> Config:
    defaults = {
        "base_url": "https://matrix.example.com",
        "room_id": "!room:example.com",
        "domain": "example.com",
    }
    defaults.update(overrides)
    return Config(**defaults)


@contextmanager
def _make_client(config):
    app.dependency_overrides[_get_config] = lambda: config
    app.state.config = config
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.mark.usefixtures("_mock_tokens")
class TestHealthyMatrix:
    def test_reachable_returns_200(self):
        config = _make_config()
        with _make_client(config) as client:
            with patch("matrix_webhook_bridge.server._matrix_probe"):
                resp = client.get("/healthy/matrix")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok", "base_url": "https://matrix.example.com"}

    def test_unreachable_returns_503(self):
        config = _make_config()
        with _make_client(config) as client:
            with patch(
                "matrix_webhook_bridge.server._matrix_probe",
                side_effect=URLError("Name or service not known"),
            ):
                resp = client.get("/healthy/matrix")
        assert resp.status_code == 503
        body = resp.json()
        assert body["detail"]["status"] == "error"
        assert body["detail"]["base_url"] == "https://matrix.example.com"
        assert "Name or service not known" in body["detail"]["detail"]
