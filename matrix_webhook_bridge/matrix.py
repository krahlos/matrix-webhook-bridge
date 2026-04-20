import json
import logging
import time
from functools import lru_cache
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


_SECRETS_DIR = "/run/secrets"


def _token_path(user: str) -> str:
    return f"{_SECRETS_DIR}/{user}_as_token.txt"


@lru_cache
def _token(path: str) -> str:
    return open(path).read().strip()


def notify(
    base_url: str, room_id: str, plain: str, html: str, token_file: str, user_id: str
) -> None:
    """Send a message to the Matrix room."""
    txn = int(time.time() * 1000)
    url = (
        f"{base_url}/_matrix/client/v3/rooms/{quote(room_id, safe='')}"
        f"/send/m.room.message/{txn}?user_id={quote(user_id, safe='')}"
    )
    body = json.dumps(
        {
            "msgtype": "m.text",
            "body": plain,
            "format": "org.matrix.custom.html",
            "formatted_body": html,
        }
    ).encode()
    req = Request(
        url,
        data=body,
        method="PUT",
        headers={
            "Authorization": f"Bearer {_token(token_file)}",
            "Content-Type": "application/json",
        },
    )
    logger.debug(f"Sending Matrix message as {user_id}: {plain}")
    try:
        with urlopen(req) as r:
            r.read()
    except HTTPError as e:
        # The JSON body carries the real reason (errcode, error, retry_after_ms).
        # str(e) is only the status line, so include the body in the log and in
        # the re-raised exception so callers see it too.
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001 - best-effort; never let logging crash the send path
            body = ""
        logger.error(
            "Matrix send failed (%s %s): %s",
            e.code,
            e.reason,
            body,
        )
        raise HTTPError(e.url, e.code, f"{e.reason}: {body}", e.headers, None) from e
    logger.info(f"Matrix message sent as {user_id}")
