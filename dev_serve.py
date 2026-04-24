"""Dev shim: redirects _SECRETS_DIR to ./secrets before startup.

Usage:
    uv run python dev_serve.py serve --config bridge.yml.example
"""

from pathlib import Path

# Patch before any bridge module uses the value
import matrix_webhook_bridge.matrix as _m
import matrix_webhook_bridge.server as _s

_secrets = str(Path(__file__).parent / "secrets")
_m._SECRETS_DIR = _secrets
_s._SECRETS_DIR = _secrets

# Create the secrets directory if it doesn't exist
Path(_secrets).mkdir(exist_ok=True)

# Create a fake token for the default user if it doesn't exist
default_user_token_path = Path(_m._token_path("bridge"))
if not default_user_token_path.is_file():
    default_user_token_path.write_text("fake_token_for_dev")

from matrix_webhook_bridge.cli import main  # noqa: E402

main()
