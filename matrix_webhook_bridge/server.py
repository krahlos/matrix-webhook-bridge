import asyncio
import hmac
import json
import logging
import re
import signal
import threading
import time
from contextlib import asynccontextmanager
from importlib.metadata import version
from typing import cast
from uuid import uuid4

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from prometheus_client import make_asgi_app

from . import metrics
from .config import LOCALPART_PATTERN, ROOM_ID_PATTERN, Config
from .formatters import SERVICES, format_generic
from .log import request_id as _request_id
from .matrix import available_tokens as _available_tokens
from .matrix import clear_token_cache as _clear_token_cache
from .matrix import join_room as _join_room
from .matrix import notify as _matrix_notify
from .matrix import probe as _matrix_probe
from .matrix import token_exists as _token_exists
from .matrix import token_path as _token_path

logger = logging.getLogger(__name__)

_start_time = time.monotonic()
_VALID_LOCALPART_RE = re.compile(LOCALPART_PATTERN)
_VALID_ROOM_ID_RE = re.compile(ROOM_ID_PATTERN)

_TAGS = [
    {
        "name": "health",
        "description": "Liveness and readiness probes.",
    },
    {
        "name": "notifications",
        "description": "Forward webhook payloads to Matrix rooms.",
    },
]


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

    if not _VALID_ROOM_ID_RE.match(config.room_id):
        raise RuntimeError(f"Invalid room_id '{config.room_id}'. Must match ^![^:]+:.+$ format.")

    for svc, rooms in config.service_rooms.items():
        for room_id in rooms:
            if not _VALID_ROOM_ID_RE.match(room_id):
                raise RuntimeError(
                    f"Invalid room_id '{room_id}' for service '{svc}' in service_rooms. "
                    f"Must match ^![^:]+:.+$ format."
                )

    if not _token_exists(config.default_user):
        raise RuntimeError(
            f"Required secret not found: {_token_path(config.default_user)}. "
            f"Cannot start server without appservice token for default user "
            f"'{config.default_user}'."
        )

    scan = _available_tokens()
    for entry in scan.invalid:
        logger.warning(
            "Secret file does not follow naming convention <name>_as_token.txt: %s",
            entry,
        )

    logger.info("Available appservice tokens: %s", ", ".join(scan.valid))


def _autojoin_all(config: Config) -> None:
    users_rooms: dict[str, set[str]] = {config.default_user: {config.room_id}}
    for svc in set(config.service_rooms) | set(config.service_users):
        user = resolve_user(svc, config)
        rooms = resolve_rooms(svc, None, config)
        users_rooms.setdefault(user, set()).update(rooms)

    for user, room_set in users_rooms.items():
        user_id = f"@{user}:{config.domain}"
        for room_id in sorted(room_set):
            try:
                _join_room(
                    config.base_url,
                    room_id,
                    _token_path(user),
                    user_id,
                    config.matrix_timeout,
                )
            except Exception as e:
                logger.error(
                    "autojoin failed",
                    extra={"user": user, "room": room_id, "error": str(e)},
                )


def resolve_user(service: str | None, config: Config) -> str:
    return config.service_users.get(service, config.default_user)


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
    config = app.state.config
    _pre_flight_check(config)
    if config.autojoin:
        await asyncio.to_thread(_autojoin_all, config)
    if threading.current_thread() is threading.main_thread():
        loop = asyncio.get_running_loop()

        def _on_sighup() -> None:
            _clear_token_cache()
            logger.info("Token cache cleared via SIGHUP")

        loop.add_signal_handler(signal.SIGHUP, _on_sighup)
    yield


app = FastAPI(
    title="Matrix Webhook Bridge",
    description=(
        "Receives webhook POST requests and forwards formatted messages "
        "to one or more Matrix rooms via the Matrix Application Service API."
    ),
    version=version("matrix-webhook-bridge"),
    openapi_tags=_TAGS,
    lifespan=_lifespan,
)

app.mount("/metrics", make_asgi_app())


def _get_config(request: Request) -> Config:
    return cast(Config, request.app.state.config)


def _check_auth(
    request: Request,
    config: Config = Depends(_get_config),
) -> None:
    if not config.webhook_secret:
        return
    auth = request.headers.get("Authorization", "")
    if not hmac.compare_digest(auth, f"Bearer {config.webhook_secret}"):
        metrics.auth_failure_total.inc()
        raise HTTPException(status_code=401)


@app.get("/healthy", summary="Server health check", tags=["health"])
def healthy(config: Config = Depends(_get_config)):
    """Return server status and uptime."""
    uptime = _format_uptime(int(time.monotonic() - _start_time))
    return {"status": "ok", "uptime": uptime}


@app.get("/version", summary="Application version", tags=["health"])
def app_version():
    """Return the current application version from package metadata."""
    return {"version": version("matrix-webhook-bridge")}


@app.get(
    "/healthy/matrix",
    summary="Matrix homeserver health check",
    tags=["health"],
    responses={503: {"description": "Matrix homeserver is unreachable"}},
)
async def healthy_matrix(config: Config = Depends(_get_config)):
    """Probe the configured Matrix homeserver and return its reachability status."""
    try:
        await asyncio.to_thread(_matrix_probe, config.base_url, config.matrix_timeout)
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail={"status": "error", "base_url": config.base_url, "detail": str(e)},
        )
    return {"status": "ok", "base_url": config.base_url}


@app.post(
    "/notify",
    summary="Send a webhook notification to Matrix",
    tags=["notifications"],
    responses={
        400: {"description": "Request body is not valid JSON"},
        401: {"description": "Missing or invalid Authorization header"},
        413: {"description": "Request body exceeds 1 MiB"},
        500: {"description": "One or more Matrix deliveries failed"},
    },
)
async def notify(
    request: Request,
    service: str | None = Query(
        None,
        description="Service name; selects the formatter, sending user, and target rooms",
    ),
    room: str | None = Query(
        None,
        description="Target room ID (e.g. !abc:example.com); overrides service_rooms",
    ),
    config: Config = Depends(_get_config),
    _: None = Depends(_check_auth),
):
    """Forward a webhook payload to one or more Matrix rooms.

    The service parameter selects the formatter (defaults to generic), the
    sending user (from service_users), and target rooms (from service_rooms).
    The room parameter overrides target room selection regardless of service_rooms.
    """
    _request_id.set(uuid4().hex[:8])
    metrics.requests_total.labels(service=service or "").inc()

    body = await request.body()
    if len(body) > 1_048_576:
        metrics.invalid_payload_total.labels(service=service or "").inc()
        raise HTTPException(status_code=413)
    try:
        data = json.loads(body)
    except Exception:
        metrics.invalid_payload_total.labels(service=service or "").inc()
        raise HTTPException(status_code=400)

    user = resolve_user(service, config)
    format_fn = SERVICES.get(service, format_generic) if service else format_generic
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
                metrics.notify_success_total.labels(service=service or "").inc()
            except Exception as e:
                logger.error(
                    "notify failed",
                    extra={"service": service, "user": user, "room": room_id, "error": str(e)},
                )
                metrics.notify_failure_total.labels(service=service or "").inc()
                failed = True

    if failed:
        raise HTTPException(status_code=500)


def run_server(config: Config) -> None:
    app.state.config = config
    logger.info(f"Starting Matrix notifier server on port {config.port}...")
    uvicorn.run(app, host="", port=config.port, access_log=False, log_config=None)
