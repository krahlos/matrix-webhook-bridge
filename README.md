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

See [INSTALL.md](INSTALL.md) for health checks and configuration reference.

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
| `room`    | Sends to this Matrix room ID, overriding any server-side routing                       |

The sender (Matrix user localpart and token) is determined server-side: the `service_users` map
in `bridge.yml` maps each service name to its user localpart. If the service is not listed,
`default_user` is used.

## Multi-room routing

By default all messages go to the global `room_id` in `bridge.yml`. You can route per service
by adding a `service_rooms` map under `server:`:

```yaml
server:
  service_rooms:
    alertmanager:
      - "!abc123:matrix.example.org"
      - "!def456:matrix.example.org"
    borgmatic:
      - "!abc123:matrix.example.org"
```

Room resolution order (first match wins):

1. `?room=<id>` — message is sent to exactly this one room, ignoring any config
2. `service_rooms[service]` — message is sent to all rooms listed for the service
3. `matrix.room_id` — fallback, single room

## Built-in formatters

| Service                  | `?service=` value | Description                                              |
| ------------------------ | ----------------- | -------------------------------------------------------- |
| Prometheus Alertmanager  | `alertmanager`    | Colour-coded alerts with severity, description and links |
