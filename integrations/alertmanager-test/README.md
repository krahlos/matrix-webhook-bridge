# Alertmanager smoke test for matrix-webhook-bridge

A script that runs a nightly end-to-end connectivity check for the
Alertmanager → `matrix-webhook-bridge` → Matrix pipeline.

At 04:00 the script fires a test alert against the Alertmanager API, waits
for Alertmanager to forward it to the bridge, then verifies that the bridge's
`bridge_notify_success_total` counter increased. The alert is resolved
immediately afterwards. If the counter did not increase the script exits with
status 1, which systemd records as a failed unit.

## Assumptions

- Alertmanager is reachable at `http://localhost:9093` (configurable via
  `ALERTMANAGER_URL`). It may run natively or as a container with the API
  port exposed on the host.
- `matrix-webhook-bridge` is reachable at `http://localhost:5001`
  (configurable via `MATRIX_WEBHOOK_BRIDGE_URL`).
- Alertmanager has a receiver that routes `severity=critical` alerts to
  `matrix-webhook-bridge` at `POST /notify?service=alertmanager`. The test
  alert carries `severity: critical`; if your routing rules use a different
  label or value, adjust the `_TEST_LABELS` dict in the script accordingly.
- `WAIT_SECONDS` (default `20`) must be at least as large as the
  `group_wait` value in your Alertmanager route config. Increase it if
  Alertmanager is slow to flush.
- The bridge exposes Prometheus metrics at `GET /metrics` on the same port
  as the webhook endpoint (enabled by default, no authentication required).
  The script uses these metrics for end-to-end verification; if `/metrics`
  is unavailable the check is skipped and the script exits 0.
- If `server.webhook_secret` is set on the bridge, Alertmanager must supply
  the secret via the `Authorization` header in its webhook config. The smoke
  test script calls Alertmanager only, not the bridge directly, so no secret
  configuration is needed here.

## Add a Matrix Application Service

Follow the instructions in the [MATRIX.md](../../MATRIX.md) guide to set up
a Matrix Application Service for Alertmanager and invite the bot user to a
room on your Synapse server.

## Setup

Copy the script and systemd units to the appropriate locations and make the
script executable:

```bash
curl \
  -L https://raw.githubusercontent.com/krahlos/matrix-webhook-bridge/main/integrations/alertmanager-test/alertmanager-test.py \
  -o /usr/local/bin/alertmanager-test.py
chmod +x /usr/local/bin/alertmanager-test.py

curl \
  -L https://raw.githubusercontent.com/krahlos/matrix-webhook-bridge/main/integrations/alertmanager-test/alertmanager-test.service \
  -o /etc/systemd/system/alertmanager-test.service

curl \
  -L https://raw.githubusercontent.com/krahlos/matrix-webhook-bridge/main/integrations/alertmanager-test/alertmanager-test.timer \
  -o /etc/systemd/system/alertmanager-test.timer
```

Then enable and start the timer:

```bash
systemctl daemon-reload
systemctl enable --now alertmanager-test.timer
```

The timer defaults to `04:00` daily. To change the schedule, override the
timer:

```bash
systemctl edit alertmanager-test.timer
```

```ini
[Timer]
OnCalendar=
OnCalendar=03:30
```

To run the test immediately:

```bash
systemctl start alertmanager-test.service
journalctl -u alertmanager-test.service
```

## Configuration

| Variable                    | Default                 | Description                                      |
| --------------------------- | ----------------------- | ------------------------------------------------ |
| `ALERTMANAGER_URL`          | `http://localhost:9093` | Alertmanager base URL                            |
| `MATRIX_WEBHOOK_BRIDGE_URL` | `http://localhost:5001` | Bridge base URL (used for metric verification)   |
| `WAIT_SECONDS`              | `20`                    | Seconds to wait after firing before verifying    |

## Example Notifications

The test produces two Matrix messages per run — one when the alert fires and
one when it resolves.

Firing:

```text
🔥 [CRITICAL] Alertmanager smoke test (since 2026-04-26T04:00:01.054Z)
Nightly connectivity check — safe to ignore.
Since: 2026-04-26T04:00:01.054Z
View in Alertmanager
```

Resolved:

```text
✅ [CRITICAL] Alertmanager smoke test (since 2026-04-26T04:00:01.054Z)
Nightly connectivity check — safe to ignore.
Since: 2026-04-26T04:00:01.054Z
View in Alertmanager
```

The "View in Alertmanager" link appears when `--web.external-url` is set in
Alertmanager's startup flags.
