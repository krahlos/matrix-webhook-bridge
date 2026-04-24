import logging

import pytest

from matrix_webhook_bridge.config_loader import load_config_from_yaml


@pytest.fixture
def config_file(tmp_path):
    """Minimal valid config file."""

    def _write(webhook_secret=None):
        secret_block = f"server:\n  webhook_secret: {webhook_secret}\n" if webhook_secret else ""
        (tmp_path / "bridge.yml").write_text(
            f"matrix:\n"
            f"  base_url: https://matrix.example.com\n"
            f"  room_id: '!room:example.com'\n"
            f"  domain: example.com\n"
            f"{secret_block}"
        )
        return str(tmp_path / "bridge.yml")

    return _write


@pytest.fixture
def secrets_dir(tmp_path, monkeypatch):
    d = tmp_path / "secrets"
    d.mkdir()
    monkeypatch.setattr("matrix_webhook_bridge.config_loader._SECRETS_DIR", str(d))
    return d


def test_config_value_used_when_no_secret_file(config_file, secrets_dir):
    path = config_file(webhook_secret="config-secret")
    config = load_config_from_yaml(path)
    assert config.webhook_secret == "config-secret"  # pragma: allowlist secret


def test_secret_file_used_when_no_config_value(config_file, secrets_dir):
    (secrets_dir / "webhook_secret").write_text("file-secret")
    path = config_file()
    config = load_config_from_yaml(path)
    assert config.webhook_secret == "file-secret"  # pragma: allowlist secret


def test_secret_file_wins_over_config_value(config_file, secrets_dir):
    (secrets_dir / "webhook_secret").write_text("file-secret")
    path = config_file(webhook_secret="config-secret")
    config = load_config_from_yaml(path)
    assert config.webhook_secret == "file-secret"  # pragma: allowlist secret


def test_empty_secret_file_falls_through_to_config(config_file, secrets_dir):
    (secrets_dir / "webhook_secret").write_text("   ")
    path = config_file(webhook_secret="config-secret")
    config = load_config_from_yaml(path)
    assert config.webhook_secret == "config-secret"  # pragma: allowlist secret


def test_neither_source_set_gives_none(config_file, secrets_dir):
    path = config_file()
    config = load_config_from_yaml(path)
    assert config.webhook_secret is None


def test_warns_when_secret_file_overrides_config(config_file, secrets_dir, caplog):
    (secrets_dir / "webhook_secret").write_text("file-secret")
    path = config_file(webhook_secret="config-secret")
    with caplog.at_level(logging.WARNING, logger="matrix_webhook_bridge.config_loader"):
        load_config_from_yaml(path)
    assert any("takes precedence" in r.getMessage() for r in caplog.records)


def test_warns_when_secret_file_is_empty(config_file, secrets_dir, caplog):
    (secrets_dir / "webhook_secret").write_text("")
    path = config_file(webhook_secret="config-secret")
    with caplog.at_level(logging.WARNING, logger="matrix_webhook_bridge.config_loader"):
        load_config_from_yaml(path)
    assert any("empty" in r.getMessage() for r in caplog.records)


def test_info_logged_when_secret_file_loaded(config_file, secrets_dir, caplog):
    (secrets_dir / "webhook_secret").write_text("file-secret")
    path = config_file()
    with caplog.at_level(logging.INFO, logger="matrix_webhook_bridge.config_loader"):
        load_config_from_yaml(path)
    assert any("loaded from Docker secret" in r.getMessage() for r in caplog.records)


def test_secret_file_value_is_stripped(config_file, secrets_dir):
    (secrets_dir / "webhook_secret").write_text("  file-secret\n")
    path = config_file()
    config = load_config_from_yaml(path)
    assert config.webhook_secret == "file-secret"  # pragma: allowlist secret
