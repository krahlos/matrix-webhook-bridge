import http.client
import io
import json
import logging
import threading
import time
from email.message import Message as HTTPMessage
from functools import lru_cache
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from uuid import uuid4

VERSIONS_PATH = "/_matrix/client/versions"

logger = logging.getLogger(__name__)

_TOKENS_DIR = "/tokens"
_RETRY_DELAYS = (1, 2, 4)  # seconds before attempts 2, 3, 4


def _token_path(user: str) -> str:
    return f"{_TOKENS_DIR}/{user}_as_token.txt"


@lru_cache
def _token(path: str) -> str:
    return open(path).read().strip()


class _KeepAliveConnection:
    """Keep-alive HTTP(S) connection to one host, reused across requests.

    Exists to avoid a TCP+TLS handshake per request, which dominated CPU
    during notification bursts (#95). A lock serializes requests because
    http.client connections are not thread-safe; a connection dropped by
    the server (idle keep-alive timeout) is reopened and retried once.

    ponytail: one serialized connection per host caps throughput at
    1/RTT msg/s; switch to a small per-user connection pool if burst
    latency ever matters.
    """

    def __init__(self, base_url: str):
        parts = urlsplit(base_url)
        self._cls = (
            http.client.HTTPSConnection if parts.scheme == "https" else http.client.HTTPConnection
        )
        self._netloc = parts.netloc
        self._lock = threading.Lock()
        self._conn: http.client.HTTPConnection | None = None

    def request(self, method: str, path: str, body: bytes | None, headers: dict, timeout: int):
        with self._lock:
            for attempt in (1, 2):
                if self._conn is None:
                    self._conn = self._cls(self._netloc, timeout=timeout)
                elif self._conn.sock is not None:
                    # http.client applies .timeout only at connect; adjust the
                    # live socket directly for an already-open connection.
                    self._conn.sock.settimeout(timeout)
                try:
                    self._conn.request(method, path, body=body, headers=headers)
                    resp = self._conn.getresponse()
                    return resp.status, resp.reason, resp.read()
                except (http.client.HTTPException, OSError):
                    self._conn.close()
                    self._conn = None
                    if attempt == 2:
                        raise


_connections: dict[str, _KeepAliveConnection] = {}
_connections_lock = threading.Lock()


def _connection_for(base_url: str) -> _KeepAliveConnection:
    with _connections_lock:
        conn = _connections.get(base_url)
        if conn is None:
            conn = _connections[base_url] = _KeepAliveConnection(base_url)
        return conn


def _do_request(
    base_url: str, method: str, path: str, body: bytes | None, headers: dict, timeout: int
) -> bytes:
    """Issue an HTTP request against base_url, reusing a keep-alive connection."""
    conn = _connection_for(base_url)
    try:
        status, reason, data = conn.request(method, path, body, headers, timeout)
    except (http.client.HTTPException, OSError) as e:
        raise URLError(e) from e
    if status >= 400:
        raise HTTPError(base_url + path, status, reason, HTTPMessage(), io.BytesIO(data))
    return bytes(data)


def _with_retry(fn):
    """Call fn(), retrying on transient 5xx/network errors using _RETRY_DELAYS."""
    delays = iter(_RETRY_DELAYS)
    while True:
        try:
            return fn()
        except HTTPError as e:
            try:
                err_body = e.read().decode("utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                err_body = ""
            wrapped = HTTPError(e.url, e.code, f"{e.reason}: {err_body}", e.headers, None)
            if e.code < 500:
                logger.error("Matrix request failed (%s %s): %s", e.code, e.reason, err_body)
                raise wrapped from e
            delay = next(delays, None)
            if delay is None:
                logger.error("Matrix request failed (%s %s): %s", e.code, e.reason, err_body)
                raise wrapped from e
            logger.warning(
                "Matrix request failed (%s %s), retrying in %ds: %s",
                e.code,
                e.reason,
                delay,
                err_body,
            )
        except URLError as e:
            delay = next(delays, None)
            if delay is None:
                logger.error("Matrix request failed: %s", e)
                raise
            logger.warning("Matrix request failed (%s), retrying in %ds", e, delay)
        time.sleep(delay)


def join_room(
    base_url: str,
    room_id: str,
    token_file: str,
    user_id: str,
    timeout: int = 5,
) -> None:
    """Join a Matrix room as user_id."""
    path = (
        f"/_matrix/client/v3/join/{quote(room_id, safe='')}"
        f"?user_id={quote(user_id, safe='')}"
    )

    def attempt():
        headers = {
            "Authorization": f"Bearer {_token(token_file)}",
            "Content-Type": "application/json",
        }
        logger.debug("Joining room %s as %s", room_id, user_id)
        _do_request(base_url, "POST", path, b"{}", headers, timeout)
        logger.info("Joined room %s as %s", room_id, user_id)

    _with_retry(attempt)


def probe(base_url: str, timeout: int = 5) -> None:
    """GET /_matrix/client/versions to check homeserver reachability."""
    _do_request(base_url, "GET", VERSIONS_PATH, None, {}, timeout)


def notify(
    base_url: str,
    room_id: str,
    plain: str,
    html: str,
    token_file: str,
    user_id: str,
    timeout: int = 5,
) -> None:
    """Send a message to the Matrix room."""
    txn = uuid4().hex
    path = (
        f"/_matrix/client/v3/rooms/{quote(room_id, safe='')}"
        f"/send/m.room.message/{txn}?user_id={quote(user_id, safe='')}"
    )
    payload = json.dumps(
        {
            "msgtype": "m.text",
            "body": plain,
            "format": "org.matrix.custom.html",
            "formatted_body": html,
        }
    ).encode()

    def attempt():
        headers = {
            "Authorization": f"Bearer {_token(token_file)}",
            "Content-Type": "application/json",
        }
        logger.debug("Sending Matrix message as %s: %s", user_id, plain)
        _do_request(base_url, "PUT", path, payload, headers, timeout)
        logger.info("Matrix message sent as %s", user_id)

    _with_retry(attempt)
