"""matrix-webhook-bridge CLI."""

import argparse
import json
import os
import sys
from urllib.request import Request, urlopen

_DEFAULT_MESSAGE = "👾 Hello, World! Sent via webhook!"


def _cmd_serve(args: argparse.Namespace) -> None:
    from .config_loader import ConfigError, load_config_from_yaml
    from .log import setup_logging
    from .server import run_server

    setup_logging()

    try:
        config = load_config_from_yaml(args.config)
    except FileNotFoundError:
        print(f"error: configuration file not found: {args.config}", file=sys.stderr)
        sys.exit(1)
    except ConfigError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

    run_server(config)


def _cmd_healthcheck(args: argparse.Namespace) -> None:
    port = args.port or int(os.environ.get("PORT", 5001))
    try:
        urlopen(f"http://localhost:{port}/healthy")  # nosec B310  # localhost only
    except Exception:
        sys.exit(1)


def _cmd_say_hello(args: argparse.Namespace) -> None:
    url = f"http://{args.host}:{args.port}/notify?user={args.user}"
    body = json.dumps({"body": args.message}).encode()
    req = Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
    try:
        with urlopen(req) as r:  # nosec B310  # URL is user-supplied CLI arg
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
        "--config",
        "-c",
        required=True,
        metavar="PATH",
        help="Path to YAML configuration file",
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
