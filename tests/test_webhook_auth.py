"""Tests for webhook authentication."""

from contextlib import contextmanager
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

from matrix_webhook_bridge.config import Config
from matrix_webhook_bridge.server import _get_config, app


@pytest.fixture
def _mock_tokens(tmp_path, monkeypatch):
    """Create a fake tokens dir with a bridge token."""
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


@pytest.fixture
def _mock_notify():
    with patch("matrix_webhook_bridge.server._matrix_notify") as m:
        yield m


@contextmanager
def _make_client(config):
    app.dependency_overrides[_get_config] = lambda: config
    app.state.config = config
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.mark.usefixtures("_mock_tokens", "_mock_notify")
class TestWebhookAuth:
    def test_no_secret_allows_all(self):
        """Without webhook_secret, requests need no auth."""
        config = _make_config()
        with _make_client(config) as client:
            resp = client.post("/notify", json={"body": "test"})
            assert resp.status_code == 200

    def test_secret_rejects_missing_header(self):
        """With webhook_secret, missing Authorization returns 401."""
        config = _make_config(webhook_secret="s3cret")
        with _make_client(config) as client:
            resp = client.post("/notify", json={"body": "test"})
            assert resp.status_code == 401

    def test_secret_rejects_wrong_token(self):
        """With webhook_secret, wrong token returns 401."""
        config = _make_config(webhook_secret="s3cret")
        with _make_client(config) as client:
            resp = client.post(
                "/notify",
                json={"body": "test"},
                headers={"Authorization": "Bearer wrong"},
            )
            assert resp.status_code == 401

    def test_secret_accepts_correct_token(self):
        """With webhook_secret, correct Bearer token returns 200."""
        config = _make_config(webhook_secret="s3cret")
        with _make_client(config) as client:
            resp = client.post(
                "/notify",
                json={"body": "test"},
                headers={"Authorization": "Bearer s3cret"},
            )
            assert resp.status_code == 200

    def test_healthcheck_unauthenticated(self):
        """GET /healthy never requires auth."""
        config = _make_config(webhook_secret="s3cret")
        with _make_client(config) as client:
            resp = client.get("/healthy")
            assert resp.status_code == 200
