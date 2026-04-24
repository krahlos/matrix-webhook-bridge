import asyncio
import hmac
import json
import logging
import os
import re
import signal
import threading
import time
from contextlib import asynccontextmanager
from uuid import uuid4

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request

from .config import Config
from .formatters import SERVICES, format_generic
from .log import request_id as _request_id
from .matrix import _SECRETS_DIR, _token, _token_path
from .matrix import notify as _matrix_notify
from .matrix import probe as _matrix_probe

logger = logging.getLogger(__name__)

_start_time = time.monotonic()
_AS_TOKEN_RE = re.compile(r"^(.+)_as_token\.txt$")
_VALID_LOCALPART_RE = re.compile(r"^[a-z0-9._\-]+$")
_VALID_ROOM_ID_RE = re.compile(r"^![^:]+:.+$")


def _pre_flight_check(config: Config) -> None:
    logger.info("Performing pre-flight check...")

    if not _VALID_LOCALPART_RE.match(config.default_user):
        raise RuntimeError(
            f"Invalid default_user '{config.default_user}'. "
            f"Must match [a-z0-9._-]+ to prevent path traversal."
        )

    for svc, user in config.service_users.items():
        if not _VALID_LOCALPART_RE.match(user):
            raise RuntimeError(
                f"Invalid user '{user}' for service '{svc}' in service_users. "
                f"Must match [a-z0-9._-]+ to prevent path traversal."
            )

    for svc, rooms in config.service_rooms.items():
        for room_id in rooms:
            if not _VALID_ROOM_ID_RE.match(room_id):
                raise RuntimeError(
                    f"Invalid room_id '{room_id}' for service '{svc}' in service_rooms. "
                    f"Must match ^![^:]+:.+$ format."
                )

    default_user_token_path = _token_path(config.default_user)
    if not os.path.isfile(default_user_token_path):
        raise RuntimeError(
            f"Required secret not found: {default_user_token_path}. "
            f"Cannot start server without appservice token for default user "
            f"'{config.default_user}'."
        )

    available_tokens: list[str] = []
    try:
        entries = os.listdir(_SECRETS_DIR)
    except FileNotFoundError:
        entries = []

    for entry in sorted(entries):
        m = _AS_TOKEN_RE.match(entry)
        if m:
            available_tokens.append(m.group(1))
        else:
            logger.warning(
                "Secret file does not follow naming convention <name>_as_token.txt: %s",
                entry,
            )

    logger.info("Available appservice tokens: %s", ", ".join(available_tokens))


def resolve_rooms(
    service: str | None,
    room_param: str | None,
    config: Config,
) -> list[str]:
    if room_param:
        return [room_param]
    if service and config.service_rooms.get(service):
        return config.service_rooms[service]
    return [config.room_id]


def _format_uptime(seconds: int) -> str:
    d, rem = divmod(seconds, 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    return f"{d}d {h}h {m}m"


@asynccontextmanager
async def _lifespan(app: FastAPI):
    _pre_flight_check(app.state.config)
    if threading.current_thread() is threading.main_thread():
        loop = asyncio.get_running_loop()
        loop.add_signal_handler(
            signal.SIGHUP,
            lambda: (_token.cache_clear(), logger.info("Token cache cleared via SIGHUP")),
        )
    yield


app = FastAPI(lifespan=_lifespan)


def _get_config(request: Request) -> Config:
    return request.app.state.config


def _check_auth(
    request: Request,
    config: Config = Depends(_get_config),
) -> None:
    if not config.webhook_secret:
        return
    auth = request.headers.get("Authorization", "")
    if not hmac.compare_digest(auth, f"Bearer {config.webhook_secret}"):
        raise HTTPException(status_code=401)


@app.get("/healthy")
def healthy(config: Config = Depends(_get_config)):
    uptime = _format_uptime(int(time.monotonic() - _start_time))
    return {"status": "ok", "uptime": uptime}


@app.get("/healthy/matrix")
async def healthy_matrix(config: Config = Depends(_get_config)):
    try:
        await asyncio.to_thread(_matrix_probe, config.base_url, config.matrix_timeout)
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail={"status": "error", "base_url": config.base_url, "detail": str(e)},
        )
    return {"status": "ok", "base_url": config.base_url}


@app.post("/notify")
async def notify(
    request: Request,
    service: str | None = None,
    room: str | None = None,
    config: Config = Depends(_get_config),
    _: None = Depends(_check_auth),
):
    _request_id.set(uuid4().hex[:8])

    body = await request.body()
    if len(body) > 1_048_576:
        raise HTTPException(status_code=413)
    try:
        data = json.loads(body)
    except Exception:
        raise HTTPException(status_code=400)

    user = config.service_users.get(service) if service else None
    user = user or config.default_user
    format_fn = SERVICES.get(service, format_generic)
    user_id = f"@{user}:{config.domain}"

    logger.info(
        "POST /notify",
        extra={
            "service": service,
            "user": user,
            "client": request.client.host if request.client else "unknown",
        },
    )

    rooms = resolve_rooms(service, room, config)
    failed = False
    for plain, html in format_fn(data):
        for room_id in rooms:
            try:
                await asyncio.to_thread(
                    _matrix_notify,
                    config.base_url,
                    room_id,
                    plain,
                    html,
                    _token_path(user),
                    user_id,
                    config.matrix_timeout,
                )
            except Exception as e:
                logger.error(
                    "notify failed",
                    extra={"service": service, "user": user, "room": room_id, "error": str(e)},
                )
                failed = True

    if failed:
        raise HTTPException(status_code=500)


def run_server(config: Config) -> None:
    app.state.config = config
    logger.info(f"Starting Matrix notifier server on port {config.port}...")
    uvicorn.run(app, host="", port=config.port, access_log=False)
