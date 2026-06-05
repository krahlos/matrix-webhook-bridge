"""Tests for GET /version endpoint."""

from contextlib import contextmanager
from importlib.metadata import version

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
def test_version_endpoint_returns_package_version():
    """/version returns the version from importlib.metadata so it stays in sync with pyproject."""
    expected = version("matrix-webhook-bridge")
    with _make_client(_make_config()) as client:
        response = client.get("/version")
    assert response.status_code == 200
    assert response.json() == {"version": expected}
