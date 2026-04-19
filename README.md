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

## Improvements

**Robustness:**

- [ ] Retry on Matrix send failure — failed `urlopen` currently logs and drops the message
- [ ] Cap request body size — unconstrained `Content-Length` can exhaust memory; cap at 1 MB

**Security:**

- [ ] Lock service→user mapping server-side — caller-supplied `?user=` controls which secret is
  read; map service→user in config instead
- [ ] Add optional incoming webhook auth — check `Authorization` header against a
  `WEBHOOK_SECRET` env var to restrict who can POST

**Observability:**

- [ ] Add request ID to structured logs — correlate incoming `/notify` calls with Matrix send
  attempts

**Features:**

_Formatters for services that push structured webhook payloads — the bridge receives and
transforms them directly._

- [ ] Add support for multiple rooms per sender
- [ ] Add `diun` formatter for Diun container image update notifications
- [ ] Add `grafana` formatter for Grafana alert webhooks
- [ ] Add `uptime-kuma` formatter for Uptime Kuma monitor status notifications
- [ ] Add `gitea` formatter for Gitea/Forgejo push, PR, issue, and release events
- [ ] Add `watchtower` formatter for Watchtower container update notifications

**Integrations:**

_Scripts in `integrations/` for services that have no push webhook — they run a tool,
parse the output, and POST to the bridge themselves._

- [ ] Add Trivy integration — run scanner and forward vulnerability results
- [ ] Add Restic integration — run backup and report success/failure
- [ ] Add Fail2ban integration — notify on bans via an action script

**Developer experience:**

- [ ] Add `.env.example` — document required env vars so new contributors don't need to read
  `docker-compose.yml`
- [ ] Extend test coverage to all formatters
- [x] Document how to add a new service — formatter function, `SERVICES` registration, token
  secret, optional user mapping
