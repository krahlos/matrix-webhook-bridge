import json
import logging
import signal
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .config import Config
from .formatters import SERVICES, format_generic
from .matrix import _token, _token_path, notify

logger = logging.getLogger(__name__)

_start_time = time.monotonic()


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
                    notify(config.base_url, config.room_id, plain, html, _token_path(user), user_id)
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
