"""End-to-end test for POST /notify against a real (stub) Matrix homeserver.

Other /notify tests mock _matrix_notify directly, so the full path — auth,
formatter lookup, room/user resolution, and the actual HTTP call to the
homeserver — is never exercised together. This test replaces the homeserver
with a stub HTTP server instead of mocking anything in matrix_webhook_bridge.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from starlette.testclient import TestClient

from matrix_webhook_bridge.config import Config
from matrix_webhook_bridge.server import _get_config, app


class _StubMatrixServer:
    """A minimal HTTP server standing in for a Matrix homeserver."""

    def __init__(self):
        self.requests: list[dict] = []
        requests = self.requests

        class Handler(BaseHTTPRequestHandler):
            def do_PUT(self):
                self._record()

            def _record(self):
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                requests.append(
                    {
                        "method": self.command,
                        "path": self.path,
                        "authorization": self.headers.get("Authorization"),
                        "body": json.loads(body) if body else None,
                    }
                )
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b"{}")

            def log_message(self, format, *args):  # noqa: A002 - stdlib signature
                pass

        self._server = HTTPServer(("127.0.0.1", 0), Handler)
        self.port = self._server.server_port
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def stop(self):
        self._server.shutdown()
        self._thread.join(timeout=2)


@pytest.fixture
def stub_matrix():
    server = _StubMatrixServer()
    yield server
    server.stop()


@pytest.fixture
def _mock_tokens(tmp_path, monkeypatch):
    monkeypatch.setattr("matrix_webhook_bridge.matrix._TOKENS_DIR", str(tmp_path))
    (tmp_path / "bridge_as_token.txt").write_text("fake-as-token")


def _make_client(config):
    app.dependency_overrides[_get_config] = lambda: config
    app.state.config = config
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.usefixtures("_mock_tokens")
def test_notify_delivers_to_stub_homeserver(stub_matrix):
    config = Config(
        base_url=stub_matrix.base_url,
        room_id="!default:example.com",
        domain="example.com",
    )

    with _make_client(config) as client:
        resp = client.post("/notify", json={"body": "hello from e2e test"})
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert len(stub_matrix.requests) == 1

    req = stub_matrix.requests[0]
    assert req["method"] == "PUT"
    assert req["path"].startswith("/_matrix/client/v3/rooms/%21default%3Aexample.com/send/")
    assert "user_id=%40bridge%3Aexample.com" in req["path"]
    assert req["authorization"] == "Bearer fake-as-token"
    assert req["body"]["body"] == "hello from e2e test"


@pytest.mark.usefixtures("_mock_tokens")
def test_notify_unreachable_homeserver_returns_500(monkeypatch):
    # Skip the retry backoff (matrix.py unit tests already cover retry timing);
    # here we only care that a real connection failure surfaces as a 500.
    monkeypatch.setattr("matrix_webhook_bridge.matrix._RETRY_DELAYS", ())

    config = Config(
        base_url="http://127.0.0.1:1",  # nothing listening here
        room_id="!default:example.com",
        domain="example.com",
        matrix_timeout=1,
    )

    with _make_client(config) as client:
        resp = client.post("/notify", json={"body": "hello"})
    app.dependency_overrides.clear()

    assert resp.status_code == 500
