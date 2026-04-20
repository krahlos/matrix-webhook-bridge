# borgmatic integration for matrix-webhook-bridge

Example files for integrating [`borgmatic`][borgmatic] with `matrix-webhook-bridge`.

[borgmatic]: https://torsion.org/borgmatic/

The script is invoked by borgmatic's `after_backup` and `on_error` hooks and sends a formatted
Matrix message indicating whether the backup completed successfully or failed, including the
hostname it ran on.

## Assumptions

- `matrix-webhook-bridge` is reachable at `http://localhost:5001` (configurable via
  `MATRIX_WEBHOOK_BRIDGE_URL`).
- If `server.webhook_secret` is set on the bridge, point `BRIDGE_CONFIG` at the
  config file so the script reads the secret automatically (requires `pyyaml`).
  Alternatively, export `WEBHOOK_SECRET` directly.
- borgmatic is installed and configured on the host.

## Add a Matrix Application Service

Follow the instructions in the [MATRIX.md](../../MATRIX.md) guide to set up a Matrix
Application Service for borgmatic and invite the bot user to a room on your Synapse server.

## Setup

Copy the `notify.py` script to `/etc/borgmatic/hooks` and make it executable:

```bash
mkdir -p /etc/borgmatic/hooks
curl \
  -L https://raw.githubusercontent.com/krahlos/matrix-webhook-bridge/main/contrib/borgmatic/notify.py \
  -o /etc/borgmatic/hooks/notify.py
chmod +x /etc/borgmatic/hooks/notify.py
```

## Example Notifications

On success:

```html
<b>✅ Backup completed successfully</b> on <code>myserver</code>
```

On failure:

```html
<b>💥 Backup failed</b> on <code>myserver</code>
```

## Configuration

Add the hook to the `after_backup` and `on_error` sections of your `/etc/borgmatic.d/config.yaml`:

```yaml
after_backup:
  - /etc/borgmatic/hooks/notify.py success
on_error:
  - /etc/borgmatic/hooks/notify.py error
```
