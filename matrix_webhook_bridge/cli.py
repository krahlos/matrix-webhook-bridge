"""matrix-webhook-bridge CLI."""

import argparse
import json
import os
import sys
from urllib.request import Request, urlopen

_DEFAULT_MESSAGE = "👾 Hello, World! Sent via webhook!"


def _cmd_serve(args: argparse.Namespace) -> None:
    missing = [
        flag
        for flag, val in [
            ("--base-url / MATRIX_BASE_URL", args.base_url),
            ("--room-id / MATRIX_ROOM_ID", args.room_id),
            ("--domain / MATRIX_DOMAIN", args.domain),
        ]
        if not val
    ]
    if missing:
        print(f"error: missing required arguments: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    from .config import Config
    from .log import setup_logging
    from .server import run_server

    setup_logging()
    run_server(
        Config(
            base_url=args.base_url,
            room_id=args.room_id,
            domain=args.domain,
            port=args.port,
            default_user=args.default_user,
        )
    )


def _cmd_healthcheck(args: argparse.Namespace) -> None:
    port = args.port or int(os.environ.get("PORT", 5001))
    try:
        urlopen(f"http://localhost:{port}/healthy")
    except Exception:
        sys.exit(1)


def _cmd_say_hello(args: argparse.Namespace) -> None:
    url = f"http://{args.host}:{args.port}/notify?user={args.user}"
    body = json.dumps({"body": args.message}).encode()
    req = Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
    try:
        with urlopen(req) as r:
            r.read()
        print(f"Sent as {args.user}.")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="matrix-webhook-bridge",
        description="Webhook-to-Matrix notification bridge",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # serve
    serve = sub.add_parser("serve", help="Start the webhook bridge server")
    serve.add_argument(
        "--base-url",
        default=os.environ.get("MATRIX_BASE_URL"),
        metavar="URL",
        help="Matrix homeserver URL [env: MATRIX_BASE_URL]",
    )
    serve.add_argument(
        "--room-id",
        default=os.environ.get("MATRIX_ROOM_ID"),
        metavar="ID",
        help="Target Matrix room ID [env: MATRIX_ROOM_ID]",
    )
    serve.add_argument(
        "--domain",
        default=os.environ.get("MATRIX_DOMAIN"),
        metavar="DOMAIN",
        help="Matrix homeserver domain [env: MATRIX_DOMAIN]",
    )
    serve.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PORT", 5001)),
        help="Port to listen on [env: PORT] (default: 5001)",
    )
    serve.add_argument(
        "--default-user",
        default=os.environ.get("DEFAULT_USER", "bridge"),
        metavar="USER",
        help="Fallback Matrix user localpart [env: DEFAULT_USER] (default: bridge)",
    )

    # healthcheck
    hc = sub.add_parser("healthcheck", help="Check if the server is healthy")
    hc.add_argument(
        "--port",
        type=int,
        default=None,
        help="Server port (default: $PORT or 5001)",
    )

    # say-hello
    sh = sub.add_parser("say-hello", help="Send a test message via the bridge")
    sh.add_argument("-u", "--user", required=True, help="Matrix user localpart")
    sh.add_argument("-m", "--message", default=_DEFAULT_MESSAGE, help="Message to send")
    sh.add_argument("--host", default="localhost", help="Bridge host (default: localhost)")
    sh.add_argument("--port", type=int, default=5001, help="Bridge port (default: 5001)")

    args = parser.parse_args()

    if args.command == "serve":
        _cmd_serve(args)
    elif args.command == "healthcheck":
        _cmd_healthcheck(args)
    elif args.command == "say-hello":
        _cmd_say_hello(args)
