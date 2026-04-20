"""Tests for webhook authentication."""

import json
from http.server import HTTPServer
from threading import Thread
from unittest.mock import patch

import pytest

from matrix_webhook_bridge.config import Config
from matrix_webhook_bridge.server import _make_handler


@pytest.fixture
def _mock_secrets(tmp_path, monkeypatch):
    """Create a fake secrets dir with a bridge token."""
    monkeypatch.setattr("matrix_webhook_bridge.matrix._SECRETS_DIR", str(tmp_path))
    monkeypatch.setattr("matrix_webhook_bridge.server._SECRETS_DIR", str(tmp_path))
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
    with patch("matrix_webhook_bridge.server.notify") as m:
        yield m


def _start_server(config):
    handler = _make_handler(config)
    server = HTTPServer(("127.0.0.1", 0), handler)
    port = server.server_address[1]
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port


def _post(port, path="/notify", headers=None, body=None):
    from urllib.request import Request, urlopen

    url = f"http://127.0.0.1:{port}{path}"
    data = json.dumps(body or {"body": "test"}).encode()
    req = Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    try:
        with urlopen(req) as r:
            return r.status
    except Exception as e:
        return e.code


@pytest.mark.usefixtures("_mock_secrets", "_mock_notify")
class TestWebhookAuth:
    def test_no_secret_allows_all(self):
        """Without webhook_secret, requests need no auth."""
        config = _make_config()
        server, port = _start_server(config)
        try:
            assert _post(port) == 200
        finally:
            server.shutdown()

    def test_secret_rejects_missing_header(self):
        """With webhook_secret, missing Authorization returns 401."""
        config = _make_config(webhook_secret="s3cret")
        server, port = _start_server(config)
        try:
            assert _post(port) == 401
        finally:
            server.shutdown()

    def test_secret_rejects_wrong_token(self):
        """With webhook_secret, wrong token returns 401."""
        config = _make_config(webhook_secret="s3cret")
        server, port = _start_server(config)
        try:
            status = _post(port, headers={"Authorization": "Bearer wrong"})
            assert status == 401
        finally:
            server.shutdown()

    def test_secret_accepts_correct_token(self):
        """With webhook_secret, correct Bearer token returns 200."""
        config = _make_config(webhook_secret="s3cret")
        server, port = _start_server(config)
        try:
            status = _post(
                port,
                headers={"Authorization": "Bearer s3cret"},
            )
            assert status == 200
        finally:
            server.shutdown()

    def test_healthcheck_unauthenticated(self):
        """GET /healthy never requires auth."""
        from urllib.request import urlopen

        config = _make_config(webhook_secret="s3cret")
        server, port = _start_server(config)
        try:
            with urlopen(f"http://127.0.0.1:{port}/healthy") as r:
                assert r.status == 200
        finally:
            server.shutdown()
