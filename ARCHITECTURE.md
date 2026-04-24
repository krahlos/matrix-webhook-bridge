# Architecture

## Overview

The bridge is a FastAPI HTTP server. External services POST webhook payloads to `/notify`,
which the bridge formats and forwards to one or more Matrix rooms via the Matrix Client-Server
API.

```text
caller → POST /notify?service=X&room=Y
              │
              ├─ auth check
              ├─ format payload
              ├─ resolve target rooms
              └─ send to Matrix (per room, in thread pool)
```

---

## Startup

Before accepting requests the server runs a pre-flight check:

- validates that user localparts in the config are safe (no path traversal)
- validates room ID formats in the per-service room config
- checks that the appservice token file for the default user exists on disk

A `SIGHUP` clears the in-process token cache, allowing token rotation without a restart.

---

## Request flow (`/notify`)

### 1. Auth

The `Authorization: Bearer <token>` header is compared against `webhook_secret` using a
constant-time comparison. Skipped when `webhook_secret` is not set.

### 2. Formatting

The `?service=` query param selects a service-specific formatter. Unknown or missing services
fall back to a generic formatter that uses `body` as plain text and `html` as formatted text.

Each formatter returns a list of `(plain, html)` tuples — one per Matrix message to send.
Alertmanager, for example, emits one tuple per alert in the payload.

### 3. Room resolution

Target rooms are resolved in priority order:

1. `?room=` query param — caller overrides everything
2. per-service room list from config
3. global default room

### 4. Matrix send

For every message × every target room, the server calls the Matrix HTTP client in a thread pool
worker. This keeps the async event loop free while the synchronous HTTP call blocks.

On HTTP 5xx or network error the client retries up to 3 times with exponential back-off
(1 s, 2 s, 4 s). Client errors (4xx) are not retried.

---

## Token management

Each Matrix user has an appservice token stored in `/run/secrets/<user>_as_token.txt`. Tokens
are read once and cached in memory. `SIGHUP` invalidates the cache to force a re-read on the
next request.
