"""Tests for matrix.notify() error-logging behavior."""

import io
import json
import logging
from unittest.mock import patch
from urllib.error import HTTPError

import pytest

from matrix_webhook_bridge import matrix as matrix_mod


class _FakeContextManager:
    """Minimal context manager returning a stub response with a .read() method."""

    def __init__(self):
        self._body = b""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self._body


def test_notify_success_path(tmp_path):
    token = tmp_path / "user_as_token.txt"
    token.write_text("test-token\n")
    matrix_mod._token.cache_clear()

    with patch.object(matrix_mod, "urlopen", return_value=_FakeContextManager()):
        matrix_mod.notify(
            base_url="https://matrix.example.org",
            room_id="!room:example.org",
            plain="hello",
            html="<b>hello</b>",
            token_file=str(token),
            user_id="@bot:example.org",
            timeout=5,
        )


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
    with patch.object(matrix_mod, "urlopen", side_effect=err):
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
    with patch.object(matrix_mod, "urlopen", side_effect=err):
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
