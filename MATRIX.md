# Matrix Application Service Setup

This guide walks through registering `matrix-webhook-bridge` as a Matrix Application Service
with Synapse, so the bridge can send messages to a room by impersonating bot users without
requiring individual user accounts.

## References

- [Synapse documentation][synapse]
- [Application Service API specification][app-service-api]

[synapse]: https://element-hq.github.io/synapse/latest/index.html
[app-service-api]: https://spec.matrix.org/unstable/application-service-api/

## Integrate Application Service with Synapse

To integrate an Application Service (AS) with Synapse add a new volume to the Synapse container
and store the application service registration files there. For example, in `docker-compose.yml`:

```yaml
services:
  synapse:
    volumes:
      - ./appservices:/app/appservices
```

Then register them in the Synapse configuration (`homeserver.yaml`):

```yaml
app_service_config_files:
  - /app/appservices/bridge.yaml
```

## Create the AS token secret

Generate a token and write it to the secrets file expected by `docker-compose.yml`:

```shell
mkdir -p secrets
openssl rand -hex 32 > secrets/bridge_as_token.txt
```

The `docker-compose.yml` already mounts this as a Docker secret at
`/run/secrets/bridge_as_token.txt`. Use the same token value in the Application
Service registration file under `as_token`.

## Get compatibility token for Synapse API

Some steps below require a matrix compatibility token (`mct`). Obtain one via `mas-cli`
inside the MAS container:

```shell
docker exec <mas_container> mas-cli manage issue-compatibility-token <username>
```

## Finding the room ID

The bridge requires a room ID (e.g. `!abc123:matrix.example.com`), not an alias. Use one of
the following to find it.

If the room has an alias, resolve it without any token via the client API (`#` → `%23`, `:` → `%3A`):

```shell
curl -s "https://<matrix_base_url>/_matrix/client/v3/directory/room/%23<room_alias>%3A<domain>" \
  | jq '.room_id'
```

If the room has no alias, look it up by name via the Synapse admin API:

```shell
curl -s -H "Authorization: Bearer <admin_token>" \
  "https://<matrix_base_url>/_synapse/admin/v1/rooms?search_term=<room_name>" \
  | jq '.rooms[] | {room_id, name}'
```

## Invite the AS bot user to the room

Use the Synapse API to invite the AS bot user to a room:

```shell
curl -s -X POST \
  -H "Authorization: Bearer <user_mct>" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "@<as_user>:<matrix_base_url>"}' \
  'https://<matrix_base_url>/_matrix/client/v3/rooms/<room_id>/invite'
```

## Accept the invite with the AS token

Call the join endpoint on behalf of the AS bot user using the AS token:

```shell
curl -s -X POST \
  -H "Authorization: Bearer $(cat secrets/bridge_as_token.txt)" \
  -H "Content-Type: application/json" \
  -d '{}' \
  "https://<matrix_base_url>/_matrix/client/v3/join/<room_id>?user_id=@bridge:<domain>"
```
