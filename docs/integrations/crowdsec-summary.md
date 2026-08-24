# CrowdSec integration for matrix-webhook-bridge

A script that sends a daily [CrowdSec][crowdsec] summary to Matrix via `matrix-webhook-bridge`.

[crowdsec]: https://www.crowdsec.net/

Once a day the script runs via a systemd timer, fetches alerts and active decisions from the
local CrowdSec container using `cscli`, and sends a single formatted summary message via
`matrix-webhook-bridge`.

## Assumptions

- CrowdSec runs as a Docker container named `crowdsec` on the same host.
- `matrix-webhook-bridge` is reachable at `http://localhost:5001` (configurable via
  `MATRIX_WEBHOOK_BRIDGE_URL`).

## Add a Matrix Application Service

Follow the instructions in the
[Matrix Application Service Setup](../getting-started/matrix-setup.md) guide to set up a Matrix
Application Service for CrowdSec and invite the bot user to a room on your Synapse server.

## Setup

Copy the script and systemd units to the appropriate locations and make the script executable:

```bash
curl \
  -L https://raw.githubusercontent.com/krahlos/matrix-webhook-bridge/main/integrations/crowdsec-summary/notify-summary.py \
  -o /etc/crowdsec/notify-summary.py
chmod +x /etc/crowdsec/notify-summary.py

curl \
  -L https://raw.githubusercontent.com/krahlos/matrix-webhook-bridge/main/integrations/crowdsec-summary/crowdsec-summary.service \
  -o /etc/systemd/system/crowdsec-summary.service

curl \
  -L https://raw.githubusercontent.com/krahlos/matrix-webhook-bridge/main/integrations/crowdsec-summary/crowdsec-summary.timer \
  -o /etc/systemd/system/crowdsec-summary.timer
```

Then enable and start the timer:

```bash
systemctl daemon-reload
systemctl enable --now crowdsec-summary.timer
```

The timer defaults to `08:00` daily. To change the schedule, override the timer:

```bash
systemctl edit crowdsec-summary.timer
```

```ini
[Timer]
OnCalendar=
OnCalendar=07:30
```

## Configuration

| Variable                    | Default                  | Description                          |
| --------------------------- | ------------------------ | ------------------------------------ |
| `MATRIX_WEBHOOK_BRIDGE_URL` | `http://localhost:5001`  | Bridge base URL                      |
| `SINCE`                     | `24h`                    | Time window for alerts               |
| `TOP_TARGETS`               | `5`                      | Number of top targets to show        |
| `TOP_COUNTRIES`             | `5`                      | Number of top countries to show      |
| `TOP_OFFENDERS`             | `3`                      | Number of top offenders to show      |

## Example Notification

```text
🛡️ CrowdSec Daily Summary — 22 Apr 2026
42 bans · 38 IPs · 5 scenarios

By target:
myserver.example.com — 18 bans
  • http-crawl-non_statics
  • http-probing
mail.example.com — 12 bans
  • postfix-spam
+ 12 more

Countries:
🇨🇳CN 15 · 🇷🇺RU 8 · 🇺🇸US 6 · 🇩🇪DE 4 · 🇫🇷FR 3

Top offenders:
1.2.3.4 — 5 bans
  • CN · AS4134 CHINANET-BACKBONE
5.6.7.8 — 3 bans
  • RU · AS12389 ROSTELECOM

Active bans: 127
```
