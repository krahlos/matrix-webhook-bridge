<div align="center">

# matrix-webhook-bridge

[![Version](https://img.shields.io/github/v/release/krahlos/matrix-webhook-bridge)](https://github.com/krahlos/matrix-webhook-bridge/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Docs](https://img.shields.io/badge/docs-mkdocs--material-blue)](https://krahlos.github.io/matrix-webhook-bridge/)

[![Main](https://github.com/krahlos/matrix-webhook-bridge/actions/workflows/main.yml/badge.svg?branch=main)](https://github.com/krahlos/matrix-webhook-bridge/actions/workflows/main.yml)

[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![ty](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ty/main/assets/badge/v0.json)](https://github.com/astral-sh/ty)
[![prek](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/j178/prek/master/docs/assets/badge-v0.json)](https://github.com/j178/prek)

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

See [Installation](docs/getting-started/installation.md) for full configuration reference and
health checks.
See [Matrix Application Service Setup](docs/getting-started/matrix-setup.md) for registering the
Application Service with Synapse.

## Usage

Any HTTP client can post to `/notify`:

```sh
curl -X POST "http://localhost:5001/notify" \
     -H "Content-Type: application/json" \
     -d '{"body": "Hello from the bridge!"}'
```

See [Usage](docs/usage.md) for query parameters, multi-room routing, and autojoin.

## Integrations

The bridge ships a built-in formatter for Alertmanager and ready-to-use notification scripts for
other tools in [`integrations/`](integrations/).

| Tool | Type | `?service=` value | Description |
| -------------------------------------------------------------- | ----------------- | ------------------ | --------------------------------------------------------- |
| Prometheus Alertmanager | built-in | `alertmanager` | Colour-coded alerts with severity, description and links |
| [borgmatic](docs/integrations/borgmatic.md) | standalone script | — | Backup job success/failure notifications |
| [CrowdSec alert](docs/integrations/crowdsec-alert.md) | standalone script | — | Per-decision ban/unban alerts |
| [CrowdSec summary](docs/integrations/crowdsec-summary.md) | standalone script | — | Daily digest of top attackers and blocked IPs |

## Metrics

Prometheus metrics are exposed at `GET /metrics` on the same port as the bridge. No authentication
is required. See [Metrics](docs/metrics.md) for the full reference.

## Disclaimer

This is developed with agentic assistance -- there is no warranty of fitness
for any purpose.

It's been guided by an engineer with a passion for clean code, nice CX
and good docs, but it's still heavy in LLM output, so you may find some bugs.
