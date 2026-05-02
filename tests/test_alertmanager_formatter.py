import re

from matrix_webhook_bridge.formatters.alertmanager import format_alertmanager


def test_format_alertmanager_preserves_plain_text_message():
    payload = {
        "externalURL": "https://alerts.example",
        "alerts": [
            {
                "status": "firing",
                "labels": {"alertname": "DiskFull", "severity": "critical"},
                "annotations": {"summary": "Disk nearly full", "description": "Only 5% left"},
                "startsAt": "2026-05-02T00:00:00Z",
                "fingerprint": "abc123",
            }
        ],
    }

    [(plain, html)] = format_alertmanager(payload)

    assert plain == "🔥 [CRITICAL] Disk nearly full (since 2026-05-02T00:00:00Z)"
    assert "2026-05-02T00:00:00Z" in plain
    assert "Disk nearly full" in html
    assert "Only 5% left" in html
    assert 'href="https://alerts.example/#/alerts?fingerprint=abc123"' in html


def test_format_alertmanager_escapes_html_and_href_values():
    payload = {
        "externalURL": 'https://alerts.example/?q=" onclick="alert(1)',
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "Fallback",
                    "severity": 'critical"><script>alert(1)</script>',
                },
                "annotations": {
                    "summary": '<img src=x onerror="alert(1)">',
                    "description": '<b onclick="alert(2)">details</b>',
                },
                "startsAt": '<time onmouseover="alert(3)">now</time>',
                "fingerprint": 'abc" onclick="alert(4)',
            }
        ],
    }

    [(plain, html)] = format_alertmanager(payload)

    assert '<img src=x onerror="alert(1)">' in plain
    assert '<img src=x onerror="alert(1)">' not in html
    assert '<b onclick="alert(2)">details</b>' not in html
    assert '<time onmouseover="alert(3)">now</time>' not in html
    assert 'onclick="alert' not in html
    assert '&lt;img src=x onerror=&quot;alert(1)&quot;&gt;' in html
    assert '&lt;b onclick=&quot;alert(2)&quot;&gt;details&lt;/b&gt;' in html
    assert '&lt;time onmouseover=&quot;alert(3)&quot;&gt;now&lt;/time&gt;' in html
    href_match = re.search(r'<a href="([^"]*)">', html)
    assert href_match is not None
    assert href_match.group(1) == (
        "https://alerts.example/?q=&quot; onclick=&quot;alert(1)"
        "/#/alerts?fingerprint=abc&quot; onclick=&quot;alert(4)"
    )
