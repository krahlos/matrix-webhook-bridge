import io
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from email.message import Message as HTTPMessage
from functools import lru_cache
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from uuid import uuid4

import urllib3

VERSIONS_PATH = "/_matrix/client/versions"

logger = logging.getLogger(__name__)

_TOKENS_DIR: str = "/tokens"
_RETRY_DELAYS = (1, 2, 4)  # seconds before attempts 2, 3, 4
_AS_TOKEN_RE = re.compile(r"^(.+)_as_token\.txt$")


def token_path(user: str) -> str:
    """Return the on-disk path for user's appservice token."""
    return f"{_TOKENS_DIR}/{user}_as_token.txt"


def token_exists(user: str) -> bool:
    """Return whether user's appservice token file exists on disk."""
    return os.path.isfile(token_path(user))


@dataclass
class TokenScan:
    valid: list[str]
    invalid: list[str]


def available_tokens() -> TokenScan:
    """Scan _TOKENS_DIR for appservice token files.

    Returns the users with a correctly named token file, and the entries
    that don't follow the <user>_as_token.txt naming convention.
    """
    try:
        entries = os.listdir(_TOKENS_DIR)
    except FileNotFoundError:
        entries = []

    valid: list[str] = []
    invalid: list[str] = []
    for entry in sorted(entries):
        m = _AS_TOKEN_RE.match(entry)
        if m:
            valid.append(m.group(1))
        else:
            invalid.append(entry)
    return TokenScan(valid=valid, invalid=invalid)


def clear_token_cache() -> None:
    """Clear the cached token contents, forcing a re-read from disk."""
    _token.cache_clear()


@lru_cache
def _token(path: str) -> str:
    return open(path).read().strip()


# Pooled keep-alive connections: avoids a TCP+TLS handshake per request,
# which dominated CPU during notification bursts (#95). Retry(1) re-sends
# once when the server drops an idle keep-alive connection.
_http = urllib3.PoolManager(maxsize=4, retries=urllib3.Retry(1, backoff_factor=0))


def _do_request(
    base_url: str, method: str, path: str, body: bytes | None, headers: dict, timeout: int
) -> bytes:
    """Issue an HTTP request against base_url, reusing pooled keep-alive connections."""
    try:
        resp = _http.request(method, base_url + path, body=body, headers=headers, timeout=timeout)
    except urllib3.exceptions.HTTPError as e:
        raise URLError(e) from e
    if resp.status >= 400:
        raise HTTPError(
            base_url + path, resp.status, resp.reason or "", HTTPMessage(), io.BytesIO(resp.data)
        )
    return bytes(resp.data)


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
    path = f"/_matrix/client/v3/join/{quote(room_id, safe='')}?user_id={quote(user_id, safe='')}"

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
