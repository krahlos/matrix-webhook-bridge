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

## Requirements

- A running Matrix homeserver (Synapse) with Application Service support
- Docker and Docker Compose

## Quick start

```sh
curl -fsSL https://raw.githubusercontent.com/krahlos/matrix-webhook-bridge/main/install.sh | sh
docker compose up -d
```

See [INSTALL.md](INSTALL.md) for full configuration reference and health checks.
See [MATRIX.md](MATRIX.md) for registering the Application Service with Synapse.

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

## Autojoin rooms

When `matrix.autojoin: true` is set, the bridge joins every configured room at startup on behalf
of each bot user. This is useful after adding a new room to `service_rooms` — instead of manually
inviting each bot, the bridge handles it automatically.

```yaml
matrix:
  autojoin: true
```

The bridge derives the set of (user, room) pairs from the config:

- `default_user` joins `matrix.room_id`
- Each entry in `service_rooms` is joined by the matching `service_users` entry, or `default_user`
  if no explicit mapping exists

Joining a room the bot is already in is a no-op. A failed join is logged as an error but does not
prevent the bridge from starting.

## Integrations

The bridge ships a built-in formatter for Alertmanager and ready-to-use notification scripts for
other tools in [`integrations/`](integrations/).

| Tool                    | Type              | `?service=` value  | Description                                               |
| ----------------------- | ----------------- | ------------------ | --------------------------------------------------------- |
| Prometheus Alertmanager | built-in          | `alertmanager`     | Colour-coded alerts with severity, description and links  |
| borgmatic               | standalone script | —                  | Backup job success/failure notifications                  |
| CrowdSec                | standalone script | —                  | Per-decision ban/unban alerts                             |
| CrowdSec summary        | standalone script | —                  | Daily digest of top attackers and blocked IPs             |

## Metrics

Prometheus metrics are exposed at `GET /metrics` on the same port as the bridge. No authentication
is required.

| Metric                        | Labels    | Description                          |
| ----------------------------- | --------- | ------------------------------------ |
| `bridge_requests_total`       | `service` | Every `POST /notify` received        |
| `bridge_notify_success_total` | `service` | Matrix send succeeded                |
| `bridge_notify_failure_total` | `service` | Matrix send failed                   |
| `bridge_invalid_payload_total`| `service` | 400 Bad Request (bad JSON/oversized) |
| `bridge_auth_failure_total`   | —         | 401 Unauthorized                     |

The `service` label is the `?service=` query value, or `""` for generic requests.

```yaml
# prometheus.yml
scrape_configs:
  - job_name: matrix-webhook-bridge
    static_configs:
      - targets: ["localhost:5001"]
```
