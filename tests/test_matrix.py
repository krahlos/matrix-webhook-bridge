"""Tests for matrix.notify() and matrix.join_room() behavior."""

import io
import json
import logging
from unittest.mock import patch
from urllib.error import HTTPError

import pytest

from matrix_webhook_bridge import matrix as matrix_mod


def test_notify_success_path(tmp_path):
    token = tmp_path / "user_as_token.txt"
    token.write_text("test-token\n")
    matrix_mod._token.cache_clear()

    with patch.object(matrix_mod, "_do_request", return_value=b"") as mock_request:
        matrix_mod.notify(
            base_url="https://matrix.example.org",
            room_id="!room:example.org",
            plain="hello",
            html="<b>hello</b>",
            token_file=str(token),
            user_id="@bot:example.org",
            timeout=5,
        )
    mock_request.assert_called_once()
    assert mock_request.call_args.args[1] == "PUT"


def test_notify_http_error_includes_response_body(tmp_path, caplog):
    token = tmp_path / "user_as_token.txt"
    token.write_text("test-token\n")
    matrix_mod._token.cache_clear()

    body = json.dumps(
        {
            "errcode": "M_LIMIT_EXCEEDED",
            "error": "Too many requests",
            "retry_after_ms": 5000,
        }
    ).encode()
    err = HTTPError(
        url="https://matrix.example.org/_matrix/client/v3/rooms/!r/send/m.room.message/1",
        code=429,
        msg="Too Many Requests",
        hdrs=None,
        fp=io.BytesIO(body),
    )

    caplog.set_level(logging.ERROR)
    with patch.object(matrix_mod, "_do_request", side_effect=err):
        with pytest.raises(HTTPError) as exc_info:
            matrix_mod.notify(
                base_url="https://matrix.example.org",
                room_id="!room:example.org",
                plain="hello",
                html="<b>hello</b>",
                token_file=str(token),
                user_id="@bot:example.org",
                timeout=30,
            )

    # The body must be in the log record
    error_messages = [
        record.getMessage() for record in caplog.records if record.levelno == logging.ERROR
    ]
    assert any("M_LIMIT_EXCEEDED" in m for m in error_messages), error_messages
    assert any("retry_after_ms" in m for m in error_messages), error_messages
    assert any("Too many requests" in m for m in error_messages), error_messages

    # And in the re-raised exception's reason so callers see it too
    assert "M_LIMIT_EXCEEDED" in str(exc_info.value)


def test_notify_http_error_unreadable_body_does_not_crash(tmp_path, caplog):
    token = tmp_path / "user_as_token.txt"
    token.write_text("test-token\n")
    matrix_mod._token.cache_clear()

    class _BrokenHTTPError(HTTPError):
        def read(self):  # noqa: D401 - test double
            raise RuntimeError("socket closed")

    err = _BrokenHTTPError(
        url="https://matrix.example.org/x",
        code=500,
        msg="Server Error",
        hdrs=None,
        fp=io.BytesIO(b""),
    )

    caplog.set_level(logging.ERROR)
    with patch.object(matrix_mod, "_do_request", side_effect=err):
        with pytest.raises(HTTPError):
            matrix_mod.notify(
                base_url="https://matrix.example.org",
                room_id="!room:example.org",
                plain="hello",
                html="<b>hello</b>",
                token_file=str(token),
                user_id="@bot:example.org",
                timeout=30,
            )

    # Must have logged something even though reading the body failed
    assert any("Matrix request failed" in r.getMessage() for r in caplog.records)


def test_join_room_success_path(tmp_path):
    token = tmp_path / "user_as_token.txt"
    token.write_text("test-token\n")
    matrix_mod._token.cache_clear()

    with patch.object(matrix_mod, "_do_request", return_value=b"") as mock_request:
        matrix_mod.join_room(
            base_url="https://matrix.example.org",
            room_id="!room:example.org",
            token_file=str(token),
            user_id="@bot:example.org",
            timeout=5,
        )
    mock_request.assert_called_once()
    assert mock_request.call_args.args[1] == "POST"


def test_join_room_4xx_raises_immediately(tmp_path):
    token = tmp_path / "user_as_token.txt"
    token.write_text("test-token\n")
    matrix_mod._token.cache_clear()

    err = HTTPError(
        url="https://matrix.example.org/_matrix/client/v3/join/!room:example.org",
        code=403,
        msg="Forbidden",
        hdrs=None,
        fp=io.BytesIO(b'{"errcode":"M_FORBIDDEN"}'),
    )

    with patch.object(matrix_mod, "_do_request", side_effect=err):
        with pytest.raises(HTTPError) as exc_info:
            matrix_mod.join_room(
                base_url="https://matrix.example.org",
                room_id="!room:example.org",
                token_file=str(token),
                user_id="@bot:example.org",
                timeout=5,
            )
    assert exc_info.value.code == 403


def test_token_path_uses_tokens_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(matrix_mod, "_TOKENS_DIR", str(tmp_path))
    assert matrix_mod.token_path("alice") == f"{tmp_path}/alice_as_token.txt"


def test_token_exists(monkeypatch, tmp_path):
    monkeypatch.setattr(matrix_mod, "_TOKENS_DIR", str(tmp_path))
    (tmp_path / "alice_as_token.txt").write_text("tok")
    assert matrix_mod.token_exists("alice") is True
    assert matrix_mod.token_exists("bob") is False


def test_available_tokens_splits_valid_and_invalid(monkeypatch, tmp_path):
    monkeypatch.setattr(matrix_mod, "_TOKENS_DIR", str(tmp_path))
    (tmp_path / "alice_as_token.txt").write_text("tok")
    (tmp_path / "bob_as_token.txt").write_text("tok")
    (tmp_path / "unexpected.txt").write_text("x")

    scan = matrix_mod.available_tokens()

    assert scan.valid == ["alice", "bob"]
    assert scan.invalid == ["unexpected.txt"]


def test_available_tokens_missing_dir_returns_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(matrix_mod, "_TOKENS_DIR", str(tmp_path / "missing"))
    scan = matrix_mod.available_tokens()
    assert scan.valid == []
    assert scan.invalid == []


def test_clear_token_cache(tmp_path):
    token = tmp_path / "user_as_token.txt"
    token.write_text("first")
    path = str(token)

    matrix_mod._token.cache_clear()
    assert matrix_mod._token(path) == "first"

    token.write_text("second")
    assert matrix_mod._token(path) == "first"  # still cached

    matrix_mod.clear_token_cache()
    assert matrix_mod._token(path) == "second"
