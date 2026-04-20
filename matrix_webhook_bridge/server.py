import json
import logging
import os
import re
import signal
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .config import Config
from .formatters import SERVICES, format_generic
from .matrix import _SECRETS_DIR, _token, _token_path, notify

logger = logging.getLogger(__name__)

_start_time = time.monotonic()
_AS_TOKEN_RE = re.compile(r"^(.+)_as_token\.txt$")
_VALID_LOCALPART_RE = re.compile(r"^[a-z0-9._\-]+$")


def _validate_user_localpart(user: str, handler: BaseHTTPRequestHandler) -> bool:
    """
    Validate that user is a valid Matrix localpart to prevent path traversal.

    Returns True if valid, False otherwise. If invalid, sends 400 response.
    """
    if not _VALID_LOCALPART_RE.match(user):
        logger.warning(
            f"Invalid user localpart '{user}' from {handler.client_address}. "
            f"Must match [a-z0-9._-]+"
        )
        handler.send_response(400)
        handler.send_header("Content-Type", "text/plain")
        handler.end_headers()
        handler.wfile.write(b"Invalid user parameter. Must match [a-z0-9._-]+")
        return False
    return True


def _pre_flight_check(config: Config) -> None:
    logger.info("Performing pre-flight check...")

    if not _VALID_LOCALPART_RE.match(config.default_user):
        raise RuntimeError(
            f"Invalid default_user '{config.default_user}'. "
            f"Must match [a-z0-9._-]+ to prevent path traversal."
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


def _format_uptime(seconds: int) -> str:
    d, rem = divmod(seconds, 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    return f"{d}d {h}h {m}m"


def _make_handler(config: Config) -> type:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/healthy":
                logger.debug(f"Healthcheck from {self.client_address}")
                uptime = _format_uptime(int(time.monotonic() - _start_time))
                body = json.dumps({"status": "ok", "uptime": uptime}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                logger.warning(f"GET {self.path} not found from {self.client_address}")
                self.send_response(404)
                self.end_headers()

        def do_POST(self):
            parsed = urlparse(self.path)
            if parsed.path != "/notify":
                logger.warning(f"POST {self.path} not found from {self.client_address}")
                self.send_response(404)
                self.end_headers()
                return

            params = parse_qs(parsed.query)
            service = params.get("service", [None])[0]
            user = params.get("user", [None])[0] or service or config.default_user

            if not _validate_user_localpart(user, self):
                return

            format_fn = SERVICES.get(service, format_generic)
            user_id = f"@{user}:{config.domain}"

            logger.info(
                "POST /notify",
                extra={
                    "service": service,
                    "user": user,
                    "client": str(self.client_address),
                },
            )
            try:
                content_length = int(self.headers["Content-Length"])
                raw_data = self.rfile.read(content_length)
                data = json.loads(raw_data)
                logger.debug(f"Received data: {data}")
            except Exception as e:
                logger.error(f"Failed to parse JSON: {e}")
                self.send_response(400)
                self.end_headers()
                return

            failed = False
            for plain, html in format_fn(data):
                try:
                    notify(config.base_url, config.room_id, plain, html, _token_path(user), user_id, config.matrix_timeout)
                except Exception as e:
                    logger.error(
                        "notify failed",
                        extra={"service": service, "user": user, "error": str(e)},
                    )
                    failed = True
            self.send_response(500 if failed else 200)
            self.end_headers()

        def log_message(self, *_) -> None:
            pass

    return Handler


def run_server(config: Config) -> None:
    _pre_flight_check(config)
    signal.signal(
        signal.SIGHUP,
        lambda *_: (
            _token.cache_clear(),
            logger.info("Token cache cleared via SIGHUP"),
        ),
    )
    server = ThreadingHTTPServer(("", config.port), _make_handler(config))
    logger.info(f"Starting Matrix notifier server on port {config.port}...")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal (KeyboardInterrupt). Shutting down gracefully...")
    except Exception as e:
        logger.error(f"Server error: {e}")
    finally:
        server.server_close()
        logger.info("Matrix notifier server stopped.")
