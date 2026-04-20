"""Configuration loader for YAML-based configuration."""

from pathlib import Path

import jsonschema
import yaml

from .config import Config

# JSON Schema for configuration validation
CONFIG_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["matrix"],
    "properties": {
        "matrix": {
            "type": "object",
            "required": ["base_url", "room_id", "domain"],
            "properties": {
                "base_url": {
                    "type": "string",
                    "minLength": 1,
                    "description": "Matrix homeserver URL",
                },
                "room_id": {
                    "type": "string",
                    "minLength": 1,
                    "description": "Target Matrix room ID",
                },
                "domain": {
                    "type": "string",
                    "minLength": 1,
                    "description": "Matrix homeserver domain",
                },
                "timeout": {
                    "type": "integer",
                    "minimum": 1,
                    "default": 5,
                    "description": "Timeout for Matrix API requests in seconds",
                },
            },
            "additionalProperties": False,
        },
        "server": {
            "type": "object",
            "properties": {
                "port": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 65535,
                    "default": 5001,
                    "description": "Port to listen on",
                },
                "default_user": {
                    "type": "string",
                    "default": "bridge",
                    "description": "Fallback Matrix user localpart",
                },
                "webhook_secret": {
                    "type": "string",
                    "minLength": 1,
                    "description": "Shared secret for incoming webhook authentication",
                },
            },
            "additionalProperties": False,
        },
    },
    "additionalProperties": False,
}


class ConfigError(Exception):
    """Configuration loading or validation error."""


def load_config_from_yaml(path: str) -> Config:
    """Load configuration from YAML file.

    Args:
        path: Path to the YAML configuration file

    Returns:
        Config instance with loaded configuration

    Raises:
        FileNotFoundError: If the configuration file does not exist
        ConfigError: If the YAML is malformed or configuration is invalid
    """
    config_path = Path(path)

    # Read file
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    try:
        with open(config_path) as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigError(f"Failed to parse YAML configuration: {e}") from e

    # Validate against schema
    try:
        jsonschema.validate(data, CONFIG_SCHEMA)
    except jsonschema.ValidationError as e:
        # Format validation error message to be more user-friendly
        path_str = ".".join(str(p) for p in e.absolute_path) if e.absolute_path else "root"
        raise ConfigError(f"Invalid configuration at '{path_str}': {e.message}") from e
    except jsonschema.SchemaError as e:
        raise ConfigError(f"Schema validation error: {e.message}") from e

    # Extract values (we know they're valid now)
    matrix_section = data["matrix"]
    server_section = data.get("server", {})

    # Construct and return Config instance
    return Config(
        base_url=matrix_section["base_url"],
        room_id=matrix_section["room_id"],
        domain=matrix_section["domain"],
        matrix_timeout=matrix_section.get("timeout", 5),
        port=server_section.get("port", 5001),
        default_user=server_section.get("default_user", "bridge"),
        webhook_secret=server_section.get("webhook_secret"),
    )
