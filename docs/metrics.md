# Metrics

Prometheus metrics are exposed at `GET /metrics` on the same port as the bridge. No authentication
is required.

| Metric                         | Labels    | Description                          |
| ------------------------------ | --------- | ------------------------------------ |
| `bridge_requests_total`        | `service` | Every `POST /notify` received        |
| `bridge_notify_success_total`  | `service` | Matrix send succeeded                |
| `bridge_notify_failure_total`  | `service` | Matrix send failed                   |
| `bridge_invalid_payload_total` | `service` | 400 Bad Request (bad JSON/oversized) |
| `bridge_auth_failure_total`    | —         | 401 Unauthorized                     |

The `service` label is the `?service=` query value, or `""` for generic requests.

```yaml
# prometheus.yml
scrape_configs:
  - job_name: matrix-webhook-bridge
    static_configs:
      - targets: ["localhost:5001"]
```
