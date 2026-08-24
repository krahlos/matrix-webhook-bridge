# Usage

Any HTTP client can post to `/notify`:

```sh
# generic message
curl -X POST "http://localhost:5001/notify" \
     -H "Content-Type: application/json" \
     -d '{"body": "Hello from the bridge!"}'

# with a registered service formatter
curl -X POST "http://localhost:5001/notify?service=alertmanager" \
     -H "Content-Type: application/json" \
     -d '{"body": "plain text", "html": "<b>bold text</b>"}'
```

## Query parameters

| Parameter | Description                                                                         |
| --------- | ----------------------------------------------------------------------------------- |
| `service` | Activates a built-in formatter and selects the sender via `service_users` in config |
| `room`    | Sends to this Matrix room ID, overriding any server-side routing                    |

The sender (Matrix user localpart and token) is determined server-side: the `service_users` map
in `bridge.yml` maps each service name to its user localpart. If the service is not listed,
`default_user` is used.

## Multi-room routing

By default all messages go to the global `room_id` in `bridge.yml`. You can route per service
by adding a `service_rooms` map under `server:`:

```yaml
server:
  service_rooms:
    alertmanager:
      - "!abc123:matrix.example.org"
      - "!def456:matrix.example.org"
    borgmatic:
      - "!abc123:matrix.example.org"
```

Room resolution order (first match wins):

1. `?room=<id>` — message is sent to exactly this one room, ignoring any config
2. `service_rooms[service]` — message is sent to all rooms listed for the service
3. `matrix.room_id` — fallback, single room

## Autojoin rooms

When `matrix.autojoin: true` is set, the bridge joins every configured room at startup on behalf
of each bot user. This is useful after adding a new room to `service_rooms` — instead of manually
inviting each bot, the bridge handles it automatically.

```yaml
matrix:
  autojoin: true
```

The bridge derives the set of (user, room) pairs from the config:

- `default_user` joins `matrix.room_id`
- Each entry in `service_rooms` is joined by the matching `service_users` entry, or `default_user`
  if no explicit mapping exists

Joining a room the bot is already in is a no-op. A failed join is logged as an error but does not
prevent the bridge from starting.
