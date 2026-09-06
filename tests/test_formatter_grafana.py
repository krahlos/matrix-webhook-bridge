from matrix_webhook_bridge.formatters.grafana import format_grafana


def test_format_grafana_preserves_plain_text_message():
    payload = {
        "alerts": [
            {
                "status": "firing",
                "labels": {"alertname": "HighCPU", "severity": "critical"},
                "annotations": {"summary": "CPU high", "description": "Above 90%"},
                "startsAt": "2026-05-02T00:00:00Z",
                "dashboardURL": "https://grafana.example/d/abc",
            }
        ],
    }

    [(plain, html)] = format_grafana(payload)

    assert plain == "🔥 [CRITICAL] CPU high (since 2026-05-02T00:00:00Z)"
    assert "Above 90%" in html
    assert 'href="https://grafana.example/d/abc"' in html


def test_format_grafana_resolved_uses_check_icon():
    payload = {
        "alerts": [
            {
                "status": "resolved",
                "labels": {"alertname": "HighCPU"},
                "annotations": {},
            }
        ],
    }

    [(plain, _)] = format_grafana(payload)

    assert plain.startswith("✅")


def test_format_grafana_falls_back_to_panel_then_generator_url():
    payload = {
        "alerts": [
            {
                "status": "firing",
                "labels": {"alertname": "A"},
                "annotations": {},
                "generatorURL": "https://grafana.example/gen",
            }
        ],
    }

    [(_, html)] = format_grafana(payload)

    assert 'href="https://grafana.example/gen"' in html


def test_format_grafana_escapes_html_and_href_values():
    payload = {
        "alerts": [
            {
                "status": "firing",
                "labels": {"alertname": "A", "severity": 'critical"><script>alert(1)</script>'},
                "annotations": {
                    "summary": '<img src=x onerror="alert(1)">',
                    "description": '<b onclick="alert(2)">details</b>',
                },
                "dashboardURL": 'https://grafana.example/d/abc" onclick="alert(3)',
            }
        ],
    }

    [(plain, html)] = format_grafana(payload)

    assert '<img src=x onerror="alert(1)">' in plain
    assert '<img src=x onerror="alert(1)">' not in html
    assert '<b onclick="alert(2)">details</b>' not in html
    assert "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;" in html
    assert "&lt;b onclick=&quot;alert(2)&quot;&gt;details&lt;/b&gt;" in html
    assert 'onclick="alert' not in html
