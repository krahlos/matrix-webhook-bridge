<div align="center">

# matrix-webhook-bridge

[![Main](https://github.com/krahlos/matrix-webhook-bridge/actions/workflows/main.yml/badge.svg)](https://github.com/krahlos/matrix-webhook-bridge/actions/workflows/main.yml)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
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

## Sending messages

Any HTTP client can post to `/notify`:

```sh
# generic message
curl -X POST "http://localhost:5001/notify?user=bridge" \
     -H "Content-Type: application/json" \
     -d '{"body": "Hello from the bridge!"}'

# with HTML formatting
curl -X POST "http://localhost:5001/notify?user=bridge" \
     -H "Content-Type: application/json" \
     -d '{"body": "plain text", "html": "<b>bold text</b>"}'
```

### Query parameters

| Parameter | Description                                                          |
| --------- | -------------------------------------------------------------------- |
| `user`    | Matrix user localpart to impersonate (e.g. `bridge`)                 |
| `service` | Activates a built-in formatter; also sets the user if not specified  |

## Built-in formatters

| Service                  | `?service=` value | Description                                              |
| ------------------------ | ----------------- | -------------------------------------------------------- |
| Prometheus Alertmanager  | `alertmanager`    | Colour-coded alerts with severity, description and links |
