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
from importlib.metadata import version
from uuid import uuid4

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from prometheus_client import make_asgi_app

from . import metrics
from .config import Config
from .formatters import SERVICES, format_generic
from .log import request_id as _request_id
from .matrix import _SECRETS_DIR, _token, _token_path
from .matrix import join_room as _join_room
from .matrix import notify as _matrix_notify
from .matrix import probe as _matrix_probe

logger = logging.getLogger(__name__)

_start_time = time.monotonic()
_AS_TOKEN_RE = re.compile(r"^(.+)_as_token\.txt$")
_VALID_LOCALPART_RE = re.compile(r"^[a-z0-9._\-]+$")
_VALID_ROOM_ID_RE = re.compile(r"^![^:]+:.+$")

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


def _autojoin_all(config: Config) -> None:
    users_rooms: dict[str, set[str]] = {config.default_user: {config.room_id}}
    for svc, rooms in config.service_rooms.items():
        user = config.service_users.get(svc, config.default_user)
        users_rooms.setdefault(user, set()).update(rooms)

    for user, rooms in users_rooms.items():
        user_id = f"@{user}:{config.domain}"
        for room_id in sorted(rooms):
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
        loop.add_signal_handler(
            signal.SIGHUP,
            lambda: (_token.cache_clear(), logger.info("Token cache cleared via SIGHUP")),
        )
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
    return request.app.state.config


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
    uvicorn.run(app, host="", port=config.port, access_log=False)
