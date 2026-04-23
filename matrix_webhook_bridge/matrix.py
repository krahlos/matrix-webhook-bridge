import json
import logging
import time
from functools import lru_cache
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
from uuid import uuid4

logger = logging.getLogger(__name__)

_SECRETS_DIR = "/run/secrets"
_RETRY_DELAYS = (1, 2, 4)  # seconds before attempts 2, 3, 4


def _token_path(user: str) -> str:
    return f"{_SECRETS_DIR}/{user}_as_token.txt"


@lru_cache
def _token(path: str) -> str:
    return open(path).read().strip()


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
    url = (
        f"{base_url}/_matrix/client/v3/rooms/{quote(room_id, safe='')}"
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

    delays = iter(_RETRY_DELAYS)
    while True:
        req = Request(
            url,
            data=payload,
            method="PUT",
            headers={
                "Authorization": f"Bearer {_token(token_file)}",
                "Content-Type": "application/json",
            },
        )
        logger.debug("Sending Matrix message as %s: %s", user_id, plain)
        try:
            with urlopen(req, timeout=timeout) as r:
                r.read()
            logger.info("Matrix message sent as %s", user_id)
            return
        except HTTPError as e:
            try:
                err_body = e.read().decode("utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                err_body = ""
            wrapped = HTTPError(e.url, e.code, f"{e.reason}: {err_body}", e.headers, None)
            if e.code < 500:
                logger.error("Matrix send failed (%s %s): %s", e.code, e.reason, err_body)
                raise wrapped from e
            delay = next(delays, None)
            if delay is None:
                logger.error("Matrix send failed (%s %s): %s", e.code, e.reason, err_body)
                raise wrapped from e
            logger.warning(
                "Matrix send failed (%s %s), retrying in %ds: %s",
                e.code,
                e.reason,
                delay,
                err_body,
            )
        except URLError as e:
            delay = next(delays, None)
            if delay is None:
                logger.error("Matrix send failed: %s", e)
                raise
            logger.warning("Matrix send failed (%s), retrying in %ds", e, delay)
        time.sleep(delay)
