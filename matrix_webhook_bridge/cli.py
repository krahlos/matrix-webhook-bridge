"""matrix-webhook-bridge CLI."""

import argparse
import os
import sys


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

    args = parser.parse_args()

    if args.command == "serve":
        _cmd_serve(args)
