# CrowdSec integration for matrix-webhook-bridge

A script that polls [CrowdSec][crowdsec] for new decisions and forwards them to Matrix via `matrix-webhook-bridge`.

[crowdsec]: https://www.crowdsec.net/

Every 5 minutes, the script runs via a systemd timer, fetches recent decisions from the local
CrowdSec container using `cscli`, and sends a formatted Matrix message for each new ban or
remediation via `matrix-webhook-bridge`.

## Assumptions

- CrowdSec runs as a Docker container named `crowdsec` on the same host.
- `matrix-webhook-bridge` is reachable at `http://localhost:5001` (configurable via
  `MATRIX_WEBHOOK_BRIDGE_URL`).
- If `server.webhook_secret` is set on the bridge, point `BRIDGE_CONFIG` at the
  config file so the script reads the secret automatically (requires `pyyaml`).
  Alternatively, export `WEBHOOK_SECRET` directly.
- The script runs every 5 minutes via a systemd timer and queries decisions from the last
  `5m` (configurable via `SINCE`).

## Add a Matrix Application Service

Follow the instructions in the [MATRIX.md](../../MATRIX.md) guide to set up a Matrix
Application Service for CrowdSec and invite the bot user to a room on your Synapse server.

## Setup

Copy the script and systemd units to the appropriate locations and make the script executable:

```bash
curl \
  -L https://raw.githubusercontent.com/krahlos/matrix-webhook-bridge/main/contrib/crowdsec/notify-decisions.py \
  -o /etc/crowdsec/notify-decisions.py
chmod +x /etc/crowdsec/notify-decisions.py

curl \
  -L https://raw.githubusercontent.com/krahlos/matrix-webhook-bridge/main/contrib/crowdsec/crowdsec-decisions.service \
  -o /etc/systemd/system/crowdsec-decisions.service

curl \
  -L https://raw.githubusercontent.com/krahlos/matrix-webhook-bridge/main/contrib/crowdsec/crowdsec-decisions.timer \
  -o /etc/systemd/system/crowdsec-decisions.timer
```

Then enable and start the timer:

```bash
systemctl daemon-reload
systemctl enable --now crowdsec-decisions.timer
```

## Example Notification

```html
<b>🚫 CrowdSec ban:</b> <code>1.2.3.4</code><br>
<b>Scenario:</b> crowdsecurity/ssh-bf (5 events)<br>
<b>Target:</b> ssh://myserver.example.com<br>
<b>Country:</b> CN | <b>AS:</b> AS4134 CHINANET-BACKBONE<br>
<b>Duration:</b> 4h0m0s
```
