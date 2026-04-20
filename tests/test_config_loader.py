"""Tests for config_loader module."""

import tempfile
from pathlib import Path

import pytest

from matrix_webhook_bridge.config import Config
from matrix_webhook_bridge.config_loader import ConfigError, load_config_from_yaml


def test_load_valid_config():
    """Load a valid YAML configuration successfully."""
    yaml_content = """
matrix:
  base_url: https://matrix.example.com
  room_id: "!test:example.com"
  domain: example.com
  timeout: 10

server:
  port: 8080
  default_user: testuser
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        f.flush()
        config_path = f.name

    try:
        config = load_config_from_yaml(config_path)
        assert config.base_url == "https://matrix.example.com"
        assert config.room_id == "!test:example.com"
        assert config.domain == "example.com"
        assert config.matrix_timeout == 10
        assert config.port == 8080
        assert config.default_user == "testuser"
    finally:
        Path(config_path).unlink()


def test_load_config_missing_file():
    """FileNotFoundError raised when config file doesn't exist."""
    with pytest.raises(FileNotFoundError, match="Configuration file not found"):
        load_config_from_yaml("/nonexistent/path/config.yml")


def test_load_config_invalid_yaml():
    """ConfigError raised for malformed YAML."""
    yaml_content = """
matrix:
  base_url: https://matrix.example.com
  room_id: "!test:example.com
  domain: example.com
"""  # Missing closing quote
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        f.flush()
        config_path = f.name

    try:
        with pytest.raises(ConfigError, match="Failed to parse YAML configuration"):
            load_config_from_yaml(config_path)
    finally:
        Path(config_path).unlink()


def test_load_config_missing_required_field():
    """ConfigError raised when required field is missing."""
    yaml_content = """
matrix:
  base_url: https://matrix.example.com
  room_id: "!test:example.com"
  # domain is missing

server:
  port: 5001
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        f.flush()
        config_path = f.name

    try:
        with pytest.raises(ConfigError, match="'domain' is a required property"):
            load_config_from_yaml(config_path)
    finally:
        Path(config_path).unlink()


def test_load_config_with_defaults():
    """Optional fields use Config dataclass defaults."""
    yaml_content = """
matrix:
  base_url: https://matrix.example.com
  room_id: "!test:example.com"
  domain: example.com
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        f.flush()
        config_path = f.name

    try:
        config = load_config_from_yaml(config_path)
        assert config.base_url == "https://matrix.example.com"
        assert config.room_id == "!test:example.com"
        assert config.domain == "example.com"
        assert config.matrix_timeout == 5  # Default
        assert config.port == 5001  # Default
        assert config.default_user == "bridge"  # Default
    finally:
        Path(config_path).unlink()


def test_load_config_invalid_type():
    """ConfigError raised for wrong type (e.g., port as string)."""
    yaml_content = """
matrix:
  base_url: https://matrix.example.com
  room_id: "!test:example.com"
  domain: example.com

server:
  port: "not_a_number"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        f.flush()
        config_path = f.name

    try:
        with pytest.raises(ConfigError, match="is not of type 'integer'"):
            load_config_from_yaml(config_path)
    finally:
        Path(config_path).unlink()


def test_load_config_nested_structure():
    """Correctly parse nested YAML structure."""
    yaml_content = """
matrix:
  base_url: https://matrix.example.com
  room_id: "!test:example.com"
  domain: example.com
  timeout: 15

server:
  port: 9000
  default_user: customuser
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        f.flush()
        config_path = f.name

    try:
        config = load_config_from_yaml(config_path)
        assert isinstance(config, Config)
        assert config.base_url == "https://matrix.example.com"
        assert config.room_id == "!test:example.com"
        assert config.domain == "example.com"
        assert config.matrix_timeout == 15
        assert config.port == 9000
        assert config.default_user == "customuser"
    finally:
        Path(config_path).unlink()


def test_load_config_missing_matrix_section():
    """ConfigError raised when matrix section is missing."""
    yaml_content = """
server:
  port: 5001
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        f.flush()
        config_path = f.name

    try:
        with pytest.raises(ConfigError, match="'matrix' is a required property"):
            load_config_from_yaml(config_path)
    finally:
        Path(config_path).unlink()


def test_load_config_invalid_server_section():
    """ConfigError raised when server section is not a dict."""
    yaml_content = """
matrix:
  base_url: https://matrix.example.com
  room_id: "!test:example.com"
  domain: example.com

server: "not a dict"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        f.flush()
        config_path = f.name

    try:
        with pytest.raises(ConfigError, match="is not of type 'object'"):
            load_config_from_yaml(config_path)
    finally:
        Path(config_path).unlink()


def test_load_config_not_yaml_object():
    """ConfigError raised when YAML is not an object."""
    yaml_content = "just a string"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        f.flush()
        config_path = f.name

    try:
        with pytest.raises(ConfigError, match="is not of type 'object'"):
            load_config_from_yaml(config_path)
    finally:
        Path(config_path).unlink()


def test_load_config_invalid_port_range():
    """ConfigError raised for port outside valid range."""
    yaml_content = """
matrix:
  base_url: https://matrix.example.com
  room_id: "!test:example.com"
  domain: example.com

server:
  port: 99999
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        f.flush()
        config_path = f.name

    try:
        with pytest.raises(ConfigError, match="is greater than the maximum of 65535"):
            load_config_from_yaml(config_path)
    finally:
        Path(config_path).unlink()


def test_load_config_negative_timeout():
    """ConfigError raised for negative timeout."""
    yaml_content = """
matrix:
  base_url: https://matrix.example.com
  room_id: "!test:example.com"
  domain: example.com
  timeout: -5
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        f.flush()
        config_path = f.name

    try:
        with pytest.raises(ConfigError, match="is less than the minimum of 1"):
            load_config_from_yaml(config_path)
    finally:
        Path(config_path).unlink()


def test_load_config_empty_file():
    """ConfigError raised when YAML file is empty."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write("")
        f.flush()
        config_path = f.name

    try:
        with pytest.raises(ConfigError, match="is not of type 'object'"):
            load_config_from_yaml(config_path)
    finally:
        Path(config_path).unlink()
