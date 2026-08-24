# matrix-webhook-bridge

A lightweight HTTP bridge that receives webhook payloads and forwards them as messages to a
Matrix room, impersonating per-sender bot users via an Application Service token.

See the [project README][readme] for a quick start, request/response examples, and the
metrics reference.

[readme]: https://github.com/krahlos/matrix-webhook-bridge

## Where to start

- [Installation](getting-started/installation.md) — install via Docker Compose, configuration
  reference
- [Matrix Application Service Setup](getting-started/matrix-setup.md) — register the bridge
  with Synapse
- [Usage](usage.md) — API, multi-room routing, autojoin
- [Metrics](metrics.md) — Prometheus reference
- [Architecture](architecture.md) — request flow and internals
- [Integrations](integrations/borgmatic.md) — borgmatic, CrowdSec
