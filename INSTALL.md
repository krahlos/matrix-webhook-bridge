# Installation

## Quick start

Run the installer to download `docker-compose.yml` and create an `.env` from the example:

```sh
curl -fsSL https://raw.githubusercontent.com/krahlos/matrix-webhook-bridge/main/install.sh | sh
```

### Configure

Edit `.env` with your Matrix homeserver URL, target room ID and domain:

```sh
VERSION=v0.1.2

MATRIX_BASE_URL=https://matrix.example.com
MATRIX_ROOM_ID=!roomid:matrix.example.com
MATRIX_DOMAIN=matrix.example.com
MATRIX_TIMEOUT=5
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

| Variable          | CLI flag            | Required | Default  | Description                                    |
| ----------------- | ------------------- | -------- | -------- | ---------------------------------------------- |
| `MATRIX_BASE_URL` | `--base-url`        | yes      | —        | Matrix homeserver URL                          |
| `MATRIX_ROOM_ID`  | `--room-id`         | yes      | —        | Target room ID                                 |
| `MATRIX_DOMAIN`   | `--domain`          | yes      | —        | Homeserver domain                              |
| `MATRIX_TIMEOUT`  | `--matrix-timeout`  | no       | `5`      | Timeout for Matrix API requests (seconds)      |
| `PORT`            | `--port`            | no       | `5001`   | Port to listen on                              |
| `DEFAULT_USER`    | `--default-user`    | no       | `bridge` | Fallback sender when no `user` param is given  |

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
