<div align="center">

# matrix-webhook-bridge

[![Main](https://github.com/krahlos/matrix-webhook-bridge/actions/workflows/main.yml/badge.svg?branch=main)](https://github.com/krahlos/matrix-webhook-bridge/actions/workflows/main.yml)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Version](https://img.shields.io/github/v/release/krahlos/matrix-webhook-bridge)](https://github.com/krahlos/matrix-webhook-bridge/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

_A lightweight HTTP bridge that receives webhook payloads and forwards them
as messages to a Matrix room, impersonating per-sender bot users via an
Application Service token._

</div>

---

> [!WARNING]
> This project is in early development and should only be used internally.

## Setup

See [INSTALL.md](INSTALL.md) for adding senders, health checks, and configuration reference.

See [MATRIX.md](MATRIX.md) for setting up the Matrix Application Service and inviting the AS bot
user to the room.

Ready-to-use scripts for borgmatic, CrowdSec, and other tools are in [`integrations/`](integrations/).

## Sending messages

Any HTTP client can post to `/notify`:

```sh
# generic message
curl -X POST "http://localhost:5001/notify" \
     -H "Content-Type: application/json" \
     -d '{"body": "Hello from the bridge!"}'

# with a registered service formatter
curl -X POST "http://localhost:5001/notify?service=alertmanager" \
     -H "Content-Type: application/json" \
     -d '{"body": "plain text", "html": "<b>bold text</b>"}'
```

### Query parameters

| Parameter | Description                                                                            |
| --------- | -------------------------------------------------------------------------------------- |
| `service` | Activates a built-in formatter and selects the sender via `service_users` in config    |

The sender (Matrix user localpart and token) is determined server-side: the `service_users` map
in `bridge.yml` maps each service name to its user localpart. If the service is not listed,
`default_user` is used.

## Authorization Header

Set `webhook_secret` in `bridge.yml` to require a shared secret on every `/notify` request:

```sh
curl -X POST "http://localhost:5001/notify" \
     -H "Authorization: Bearer <your-secret>" \
     -H "Content-Type: application/json" \
     -d '{"body": "Hello"}'
```

Requests with a missing or wrong token are rejected with `401`. The `/healthy` endpoint is always
unauthenticated. If `webhook_secret` is unset, all requests are accepted without a token.

## Built-in formatters

| Service                  | `?service=` value | Description                                              |
| ------------------------ | ----------------- | -------------------------------------------------------- |
| Prometheus Alertmanager  | `alertmanager`    | Colour-coded alerts with severity, description and links |

## Adding a new service

**1. Write a formatter** in `matrix_webhook_bridge/formatters/<service>.py`. A formatter takes
the raw webhook payload and returns a list of `(plain, html)` tuples — one per Matrix message:

```python
def format_myservice(data: dict) -> list[tuple[str, str]]:
    plain = f"Event: {data['event']}"
    html = f"<b>Event:</b> {data['event']}"
    return [(plain, html)]
```

**2. Register it** in `matrix_webhook_bridge/formatters/__init__.py`:

```python
from .myservice import format_myservice

SERVICES: dict[str, callable] = {
    "alertmanager": format_alertmanager,
    "myservice": format_myservice,
}
```

**3. Add the token secret.** Create the secret file and wire it into `docker-compose.yml`:

```shell
openssl rand -hex 32 > secrets/myservice_as_token.txt
```

```yaml
secrets:
  myservice_as_token.txt:
    file: ./secrets/myservice_as_token.txt

services:
  bridge:
    secrets:
      - myservice_as_token.txt
```

The bridge will then accept `POST /notify?service=myservice` and send messages impersonating
`@myservice:<domain>` using that token.
