"""Tests for the total request deadline on POST /notify (#158).

Without it, deliveries keep retrying in their worker thread after the caller
has timed out and retried, and every retry lands in Matrix as a new message.
"""

import time
from unittest.mock import patch
from urllib.error import URLError

import pytest
from starlette.testclient import TestClient

from matrix_webhook_bridge import matrix as matrix_mod
from matrix_webhook_bridge.config import Config
from matrix_webhook_bridge.server import _get_config, app


@pytest.fixture
def _mock_tokens(tmp_path, monkeypatch):
    monkeypatch.setattr("matrix_webhook_bridge.matrix._TOKENS_DIR", str(tmp_path))
    (tmp_path / "bridge_as_token.txt").write_text("fake-as-token")


def test_notify_stops_retrying_once_deadline_passed(tmp_path):
    token = tmp_path / "bridge_as_token.txt"
    token.write_text("test-token\n")
    matrix_mod._token.cache_clear()

    # Deadline leaves no room for the first retry's 1s backoff, so the single
    # failed attempt must surface immediately instead of sleeping through it.
    started = time.monotonic()
    with patch.object(matrix_mod, "_do_request", side_effect=URLError("boom")) as mock_request:
        with pytest.raises(URLError):
            matrix_mod.notify(
                base_url="https://matrix.example.org",
                room_id="!room:example.org",
                plain="hello",
                html="<b>hello</b>",
                token_file=str(token),
                user_id="@bridge:example.org",
                timeout=5,
                deadline=time.monotonic() + 0.5,
            )

    assert mock_request.call_count == 1
    assert time.monotonic() - started < 1


@pytest.mark.usefixtures("_mock_tokens")
def test_notify_deadline_skips_remaining_rooms_and_returns_504():
    calls: list[str] = []

    def slow_notify(base_url, room_id, plain, html, token_file, user_id, timeout, deadline=None):
        calls.append(room_id)
        time.sleep(1.2)

    config = Config(
        base_url="https://matrix.example.org",
        room_id="!default:example.com",
        domain="example.com",
        request_timeout=1,
        service_rooms={"custom": ["!one:example.com", "!two:example.com"]},
    )

    app.dependency_overrides[_get_config] = lambda: config
    app.state.config = config
    with patch("matrix_webhook_bridge.server._matrix_notify", side_effect=slow_notify):
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.post("/notify?service=custom", json={"body": "hello"})
    app.dependency_overrides.clear()

    assert resp.status_code == 504
    assert calls == ["!one:example.com"]
