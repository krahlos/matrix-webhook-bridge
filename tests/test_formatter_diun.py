"""Tests for the diun webhook formatter."""

from matrix_webhook_bridge.formatters.diun import format_diun

_FULL_PAYLOAD = {
    "diun_version": "4.24.0",
    "hostname": "myserver",
    "status": "new",
    "provider": "file",
    "image": "docker.io/crazymax/diun:latest",
    "hub_link": "https://hub.docker.com/r/crazymax/diun",
    "mime_type": "application/vnd.docker.distribution.manifest.list.v2+json",
    "digest": "sha256:216e3ae7de4ca8b553eb11ef7abda00651e79e537e85c46108284e5e91673e01",
    "created": "2020-03-26T12:23:56Z",
    "platform": "linux/amd64",
    "metadata": {
        "ctn_names": "diun",
        "ctn_state": "running",
    },
}


class TestFormatDiun:
    def test_returns_single_message(self):
        result = format_diun(_FULL_PAYLOAD)
        assert len(result) == 1

    def test_new_status_icon_and_label(self):
        plain, html = format_diun(_FULL_PAYLOAD)[0]
        assert "🆕" in plain
        assert "[NEW]" in plain
        assert "🆕" in html
        assert "[NEW]" in html

    def test_update_status_icon_and_label(self):
        payload = {**_FULL_PAYLOAD, "status": "update"}
        plain, html = format_diun(payload)[0]
        assert "🔄" in plain
        assert "[UPDATE]" in plain

    def test_image_in_plain(self):
        plain, _ = format_diun(_FULL_PAYLOAD)[0]
        assert "docker.io/crazymax/diun:latest" in plain

    def test_hub_link_in_html(self):
        _, html = format_diun(_FULL_PAYLOAD)[0]
        assert 'href="https://hub.docker.com/r/crazymax/diun"' in html

    def test_hostname_and_platform_in_plain(self):
        plain, _ = format_diun(_FULL_PAYLOAD)[0]
        assert "myserver" in plain
        assert "linux/amd64" in plain

    def test_created_in_html(self):
        _, html = format_diun(_FULL_PAYLOAD)[0]
        assert "2020-03-26T12:23:56Z" in html

    def test_no_hub_link_falls_back_to_bold(self):
        payload = {**_FULL_PAYLOAD, "hub_link": ""}
        _, html = format_diun(payload)[0]
        assert "<b>" in html
        assert "<a " not in html

    def test_minimal_payload(self):
        plain, html = format_diun({"image": "alpine:latest", "status": "new"})[0]
        assert "alpine:latest" in plain
        assert "[NEW]" in plain
