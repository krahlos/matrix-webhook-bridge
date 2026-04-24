"""Tests for /notify request body size limit."""

from contextlib import contextmanager
from unittest.mock import patch

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
class TestBodySizeLimit:
    def test_body_at_limit_is_accepted(self):
        """A 1 MB body must not be rejected with 413."""
        config = _make_config()
        payload = b'{"body": "' + b"x" * (1_048_576 - 12) + b'"}'
        with _make_client(config) as client:
            with patch("matrix_webhook_bridge.server._matrix_notify"):
                resp = client.post("/notify", content=payload)
                assert resp.status_code != 413

    def test_body_over_limit_returns_413(self):
        """A body exceeding 1 MB must be rejected with 413."""
        config = _make_config()
        payload = b"x" * 1_048_577
        with _make_client(config) as client:
            resp = client.post("/notify", content=payload)
            assert resp.status_code == 413
