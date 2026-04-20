# Installation

## Quick start

Run the installer to download `docker-compose.yml` and create a `config/bridge.yml` from the example:

```sh
curl -fsSL https://raw.githubusercontent.com/krahlos/matrix-webhook-bridge/main/install.sh | sh
```

### Configure

Edit `config/bridge.yml` with your Matrix homeserver details:

```yaml
matrix:
  base_url: https://matrix.example.com
  room_id: "!roomid:matrix.example.com"
  domain: matrix.example.com
  timeout: 5

server:
  port: 5001
  default_user: bridge
```

### Add the Application Service token

```sh
mkdir secrets
echo "your_as_token_here" > secrets/bridge_as_token.txt
```

### Start

```sh
docker compose up -d
```

## Adding senders

Each sender needs its own Application Service token mounted at
`/run/secrets/<user>_as_token.txt`.

## Health check

```sh
docker compose exec bridge matrix-webhook-bridge healthcheck
```

## Configuration reference

All configuration is defined in the YAML configuration file (default: `config/bridge.yml`).

| YAML Path                | Required | Default  | Description                                 |
| ------------------------ | -------- | -------- | ------------------------------------------- |
| `matrix.base_url`        | yes      | —        | Matrix homeserver URL                       |
| `matrix.room_id`         | yes      | —        | Target room ID                              |
| `matrix.domain`          | yes      | —        | Homeserver domain                           |
| `matrix.timeout`         | no       | `5`      | Timeout for Matrix API requests (seconds)   |
| `server.port`            | no       | `5001`   | Port to listen on (see note below)          |
| `server.default_user`    | no       | `bridge` | Fallback sender when no `user` param given  |
| `server.webhook_secret`  | no       | —        | Shared secret for webhook auth (see below)  |

> [!TIP]
> When running with Docker, keep `server.port` at `5001` and remap the
> host port in `docker-compose.yml` (e.g. `"8080:5001"`).

### Webhook authentication

Set `server.webhook_secret` to require a `Bearer` token on all
incoming `POST /notify` requests:

```yaml
server:
  webhook_secret: my-secret-token
```

Clients must then include the header:

```text
Authorization: Bearer my-secret-token
```

Requests with a missing or incorrect token receive `401 Unauthorized`.
The health-check endpoint (`GET /healthy`) is never authenticated.

### CLI Usage

```sh
matrix-webhook-bridge serve --config /path/to/config.yml
```

## Alertmanager

Download the override file and add the Alertmanager token:

```sh
curl -fsSL https://raw.githubusercontent.com/krahlos/matrix-webhook-bridge/main/docker-compose.override.yml -o docker-compose.override.yml
echo "your_alertmanager_as_token_here" > secrets/alertmanager_as_token.txt
docker compose up -d
```

Then point Alertmanager's webhook receiver at:

```text
http://localhost:5001/notify?service=alertmanager
```
