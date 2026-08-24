# Installation

## Quick start

Run the installer in an **empty** directory. It downloads `docker-compose.yml`, creates
`config/bridge.yml`, generates the AS token, and bootstraps `bridge-registration.yml`. It will
refuse to run if any of those paths already exist.

```sh
curl -fsSL https://raw.githubusercontent.com/krahlos/matrix-webhook-bridge/main/install.sh | sh
```

### Manual Steps

The installer downloads `docker-compose.yml`, creates `config/bridge.yml` from the example,
generates `tokens/bridge_as_token.txt`, and bootstraps an `bridge-registration.yml` with the
token already filled in. What it cannot do is register the Application Service with your
Synapse — that must be done manually.

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

Mount the `bridge-registration.yml` as an Application Service in your Synapse:

```yaml
app_service_config_files:
  - /path/to/bridge-registration.yml
```

> [!TIP]
> Create an `applications` directory next to your `synapse/docker-compose.yml`
> and `mv` the `bridge-registration.yml` there. Then mount `/applications` as a volume
> in your Synapse and use `/applications/bridge-registration.yml` as the path in
> `app_service_config_files`.

### Start

```sh
docker compose up -d
```

## Health check

```sh
docker compose exec bridge matrix-webhook-bridge healthcheck
```

`GET /healthy` — server liveness (uptime). `GET /healthy/matrix` — homeserver reachability.
`GET /metrics` — Prometheus metrics (no auth required).

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

Alternatively, provide the secret via a Docker secret mounted at `/run/secrets/webhook_secret`.
This takes precedence over the config value:

```shell
echo "my-secret-token" > secrets/webhook_secret.txt
```

```yaml
# docker-compose.yml
secrets:
  webhook_secret:
    file: ./secrets/webhook_secret.txt

services:
  bridge:
    secrets:
      - webhook_secret
```

Requests with a missing or incorrect token receive `401 Unauthorized`.
The health-check endpoint (`GET /healthy`) is never authenticated.
