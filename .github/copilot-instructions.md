# Copilot Instructions for matrix-webhook-bridge

## Project Overview

`matrix-webhook-bridge` is a lightweight Python (FastAPI + uvicorn) HTTP bridge that
receives webhook payloads and forwards them as messages to Matrix rooms, impersonating
per-sender bot users via an Application Service token. The server exposes `POST /notify`,
`GET /healthy`, `GET /healthy/matrix`, and `GET /metrics`.

## Repository Layout

```text
matrix_webhook_bridge/   # Main application package
  cli.py                 # Entry-point: `matrix-webhook-bridge` CLI (serve / healthcheck)
  server.py              # FastAPI app, request flow, pre-flight checks, autojoin
  config.py              # Config dataclass
  config_loader.py       # YAML loader + jsonschema validation
  matrix.py              # Matrix HTTP client (notify, join_room, probe) with retry logic
  metrics.py             # Prometheus counters
  log.py                 # Logging helpers (request_id context var)
  formatters/
    __init__.py          # format_generic + SERVICES registry dict
    alertmanager.py      # Alertmanager-specific formatter
integrations/            # Standalone notification scripts (borgmatic, crowdsec-*)
tests/                   # pytest test suite
Dockerfile               # Multi-stage build (python:3.12-slim)
docker-compose.yml       # Compose deployment
bridge.yml.example       # Annotated config reference
bridge-registration.yml.example  # Matrix Application Service registration example
dev_serve.py             # Dev shim: redirects /tokens to ./tokens, creates fake token
pyproject.toml           # Build (hatchling), dependencies, ruff, mypy, bandit config
.pre-commit-config.yaml  # All linting hooks (run via pre-commit)
```

## Development Environment Setup

```sh
# Install the package with test dependencies
pip install ".[test]"

# Run tests
pytest

# Run all linters (mirrors CI)
pre-commit run --all-files

# Run individual linters
ruff check .          # pycodestyle, pyflakes, isort, pyupgrade
ruff format .         # code formatting (100-char lines, double quotes)
mypy matrix_webhook_bridge/   # type checking (Python 3.11 target)
```

### Local Development Server

```sh
# Uses dev_serve.py to redirect /tokens to ./tokens and create a fake token
uv run python dev_serve.py serve --config bridge.yml.example
```

Token files must live at `/tokens/<user>_as_token.txt` at runtime. In tests, this
directory is monkeypatched to a `tmp_path`.

## Running Tests

```sh
pytest                  # run all tests
pytest tests/test_server.py  # run a specific file
```

Tests use `starlette.testclient.TestClient` (backed by httpx) and `unittest.mock.patch`.
The `_mock_tokens` fixture monkeypatches `matrix_webhook_bridge.matrix._TOKENS_DIR` and
`matrix_webhook_bridge.server._TOKENS_DIR` to a `tmp_path`, then writes a fake token
file there. Use the same pattern in new tests that exercise server startup or `/notify`.

## Code Style and Conventions

- **Python version**: 3.11+ (CI uses 3.13). Use `X | Y` unions, `match`, etc.
- **Formatter**: ruff (`line-length = 100`, `quote-style = "double"`, `indent-style = "space"`).
- **Linting rules**: pycodestyle (E), pyflakes (F), isort (I), pyupgrade (UP).
- **Type hints**: required on all public functions; mypy is run in strict-ish mode.
- **Commit messages**: Conventional Commits enforced by pre-commit
  (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`, etc.).
- **No comments** unless they explain non-obvious logic; the existing code is largely
  self-documenting.
- **No new external dependencies** unless strictly necessary.

## Adding a New Service Formatter

1. Create `matrix_webhook_bridge/formatters/<service>.py` with a function:

   ```python
   def format_<service>(data: dict) -> list[tuple[str, str]]:
       """Returns list of (plain_text, html_text) tuples — one per Matrix message."""
       ...
   ```

2. Import and register it in `matrix_webhook_bridge/formatters/__init__.py`:

   ```python
   from .<service> import format_<service>
   SERVICES: dict[str, Formatter] = {
       "alertmanager": format_alertmanager,
       "<service>": format_<service>,
   }
   ```

3. Add tests in `tests/test_<feature>.py`.

## Key Architecture Notes

- **Room resolution order**: `?room=` param → `service_rooms[service]` → `matrix.room_id`.
- **User resolution**: `service_users[service]` → `default_user`.
- **Token files**: `/tokens/<user>_as_token.txt`; cached with `@lru_cache`; invalidated by `SIGHUP`.
- **Matrix retries**: 5xx and network errors are retried up to 3 times (1 s, 2 s, 4 s back-off);
  4xx errors are not retried.
- **Webhook auth**: constant-time `hmac.compare_digest` against `webhook_secret`; skipped when
  `webhook_secret` is absent.
- **Pre-flight check**: validates user localpart regex, room ID format, and token file existence
  before the server accepts traffic.
- **Body size limit**: 1 MiB; larger payloads return HTTP 413.
- **Autojoin**: when `matrix.autojoin: true`, the bridge calls `join_room` at startup for every
  (user, room) pair derived from the config.

## CI Workflows

| Workflow | Trigger | Jobs |
| --- | --- | --- |
| `pull_request.yml` | PR opened/updated | pre-commit checks, tests (if src changed), smoke test, image build (if Dockerfile changed) |
| `main.yml` | Push to `main` | tests, smoke test, image build |
| `publish_release.yml` | Manual run (`workflow_dispatch`) | image build + push to registry |

Tests and smoke-test are skipped on PRs that only modify non-source files (docs, configs).

## Known Workarounds

- **`GHSA-58qw-9mgm-455v`** is suppressed in `pip-audit` (vulnerability in pip itself ≤ 26.0.1,
  not a project dependency). Remove the `--ignore-vuln` flag once pip 26.0.2+ is available.

## Configuration Reference (bridge.yml)

```yaml
matrix:
  base_url: https://matrix.example.com   # required
  room_id: "!roomid:matrix.example.com"  # required; fallback room
  domain: matrix.example.com             # required; used to build @user:domain
  timeout: 5                              # seconds for Matrix API calls
  autojoin: false                         # join rooms at startup

server:
  port: 5001
  default_user: bridge                   # localpart; must match [a-z0-9._-]+
  webhook_secret: your-secret-here       # optional; also readable from /run/secrets/webhook_secret
  service_users:                         # service → user localpart
    alertmanager: alertmanager
  service_rooms:                         # service → list of room IDs
    alertmanager:
      - "!abc123:matrix.example.org"
```

Docker secret `/run/secrets/webhook_secret` takes precedence over `webhook_secret` in YAML.
