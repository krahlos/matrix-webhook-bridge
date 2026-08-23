"""Guards against notify() opening a new connection on every call.

Counts connect() calls via cProfile instead of measuring wall-clock time:
counts are deterministic, a timing threshold would flake on shared CI
runners.

Checked the test can fail: passing headers={"Connection": "close"} in
_do_request (forcing a fresh connection every time) turns the 1 connect()
below into 20, past MAX_CONNECTS.
"""

import threading
from cProfile import Profile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from matrix_webhook_bridge import matrix as matrix_mod

N_CALLS = 20
# 1 real connection + slack for a keep-alive timeout/reconnect under CI jitter.
MAX_CONNECTS = 3


class _EchoHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"  # keep-alive; default HTTP/1.0 closes per request

    def do_PUT(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *a):
        pass


@pytest.fixture
def echo_server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _EchoHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()
    thread.join()


def test_notify_reuses_connection_across_burst(tmp_path, echo_server):
    token = tmp_path / "bridge_as_token.txt"
    token.write_text("test-token\n")
    matrix_mod._token.cache_clear()
    matrix_mod._http.clear()

    profiler = Profile()
    profiler.enable()
    for _ in range(N_CALLS):
        matrix_mod.notify(
            base_url=echo_server,
            room_id="!room:example.org",
            plain="hello",
            html="<b>hello</b>",
            token_file=str(token),
            user_id="@bridge:example.org",
            timeout=5,
        )
    profiler.disable()

    connect_calls = sum(
        entry.callcount
        for entry in profiler.getstats()
        if getattr(entry.code, "co_name", entry.code) == "connect"
    )

    assert connect_calls <= MAX_CONNECTS, (
        f"expected at most {MAX_CONNECTS} socket connects for {N_CALLS} notify() "
        f"calls (keep-alive reuse), got {connect_calls} — connection is being "
        "re-established per call"
    )
