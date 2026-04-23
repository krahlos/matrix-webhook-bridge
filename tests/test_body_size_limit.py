"""Tests for /notify request body size limit."""

from http.server import HTTPServer
from threading import Thread
from unittest.mock import patch

import pytest

from matrix_webhook_bridge.config import Config
from matrix_webhook_bridge.server import _make_handler


@pytest.fixture
def _mock_secrets(tmp_path, monkeypatch):
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


def _start_server(config):
    handler = _make_handler(config)
    server = HTTPServer(("127.0.0.1", 0), handler)
    port = server.server_address[1]
    Thread(target=server.serve_forever, daemon=True).start()
    return server, port


def _post_raw(port, data: bytes):
    import http.client

    conn = http.client.HTTPConnection("127.0.0.1", port)
    conn.request(
        "POST",
        "/notify",
        body=data,
        headers={"Content-Type": "application/json", "Content-Length": str(len(data))},
    )
    resp = conn.getresponse()
    conn.close()
    return resp.status


@pytest.mark.usefixtures("_mock_secrets")
class TestBodySizeLimit:
    def test_body_at_limit_is_accepted(self):
        """A 1 MB body must not be rejected with 413."""
        config = _make_config()
        server, port = _start_server(config)
        with patch("matrix_webhook_bridge.server.notify"):
            payload = b'{"body": "' + b"x" * (1_048_576 - 12) + b'"}'
            try:
                assert _post_raw(port, payload) != 413
            finally:
                server.shutdown()

    def test_body_over_limit_returns_413(self):
        """A body exceeding 1 MB must be rejected with 413."""
        config = _make_config()
        server, port = _start_server(config)
        with patch("matrix_webhook_bridge.server.notify"):
            payload = b"x" * 1_048_577
            try:
                assert _post_raw(port, payload) == 413
            finally:
                server.shutdown()
