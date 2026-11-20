# Application Monitoring & Observability Guide

## 1. Observability Architecture Overview

The Resume Analyzer production observability stack consists of three complementary pillars:

```
+--------------------------------------------------------------------------+
|                               FASTAPI API                                |
|                                                                          |
|  [ Structured JSON Logger ]     [ Sentry SDK ]     [ Prometheus Client ]  |
|     (Correlation IDs)           (Scrubbed PII)         (/metrics)        |
+--------------------------------------------------------------------------+
            |                             |                       |
            v                             v                       v
      stdout / Docker              sentry.io / GlitchTip     Prometheus
      (Log Aggregator)             (Issue Tracking)      (Timeseries Scraping)
                                                                  |
                                                                  v
                                                               Grafana
                                                             (Dashboards)
                                                                  |
                                                                  v
                                                             Alertmanager
                                                          (Email/Slack/Pager)
```

1. **Error Tracking (Sentry):** Captures runtime exceptions, stack traces, and unhandled errors from FastAPI and Celery workers with strict PII and credential scrubbing.
2. **Metrics & Telemetry (Prometheus & Grafana):** Gathers real-time performance metrics (HTTP latency, connection pool saturation, Celery queue throughput, AI provider latency).
3. **Structured Logging:** Standardized JSON formatting with request correlation IDs and automated credential masking.
4. **Health Probes:** Distinct `/health/liveness` and `/health/readiness` endpoints preventing container restart loops.

---

## 2. Error Tracking — Sentry Integration

### 2.1 Backend Setup
Sentry is enabled on the backend by setting `SENTRY_DSN` in the environment. If unset, Sentry safely disables itself without crashing or slowing down requests.

```bash
# backend/.env or production environment
SENTRY_DSN=https://your-public-key@o000000.ingest.sentry.io/0000000
SENTRY_ENVIRONMENT=production
SENTRY_RELEASE=0.1.0
SENTRY_TRACES_SAMPLE_RATE=0.1
```

### 2.2 Data Scrubbing & Privacy Protection
The backend implements a strict `before_send` scrubber (`app/core/sentry.py`):
- **Headers Redacted:** `Authorization`, `Proxy-Authorization`, `Cookie`, `Set-Cookie`, `X-API-Key`.
- **Payload Fields Redacted:** `password`, `token`, `secret`, `secret_key`, `api_key`, `raw_resume`, `resume_content`, `vacancy_content`.
- **Candidate Data:** Personal candidate details, email addresses, and resume texts are filtered before transmission.

### 2.3 Frontend Setup (CRM & Landing)
Configured via Vite environment variables:
```bash
# crm/.env or landing/.env
VITE_SENTRY_DSN=https://your-frontend-key@o000000.ingest.sentry.io/0000001
VITE_SENTRY_ENVIRONMENT=production
```
Fatal UI errors are caught by `crm/src/components/routing/ErrorBoundary.tsx`, which logs the error, invokes `reportError()`, and presents a safe recovery UI without exposing stack traces.

---

## 3. Metrics & Prometheus Instrumentation

### 3.1 Exposition Endpoint
Metrics are exposed at `GET /metrics` in standard Prometheus text format:
```bash
curl -s http://localhost:8000/metrics | head -n 30
```

### 3.2 Metric Catalog

#### API Metrics
| Metric Name | Type | Labels | Description |
| :--- | :--- | :--- | :--- |
| `http_requests_total` | Counter | `method`, `endpoint`, `status_code` | Total HTTP requests handled |
| `http_request_duration_seconds` | Histogram | `method`, `endpoint` | Request execution latency in seconds |

> [!NOTE]
> **Cardinality Invariant:** Variable route segments like IDs or UUIDs are automatically normalized (e.g. `/api/jobs/{id}`) to prevent Prometheus memory leaks.

#### Database Pool Metrics
| Metric Name | Type | Description |
| :--- | :--- | :--- |
| `db_pool_size` | Gauge | Configured SQLAlchemy connection pool size |
| `db_pool_checked_in` | Gauge | Idle connections currently available in the pool |
| `db_pool_checked_out` | Gauge | Active connections currently leased by requests |
| `db_pool_overflow` | Gauge | Active connections created beyond base pool capacity |

#### Celery Background Processing Metrics
| Metric Name | Type | Labels | Description |
| :--- | :--- | :--- | :--- |
| `celery_task_events_total` | Counter | `task_name`, `status` | Completed task states (`SUCCESS`, `FAILURE`, `RETRY`) |
| `celery_task_duration_seconds` | Histogram | `task_name` | Task execution duration in seconds |

#### Business & AI Operation Metrics
| Metric Name | Type | Labels | Description |
| :--- | :--- | :--- | :--- |
| `resume_analyses_total` | Counter | `status` | Single resume evaluation results (`success`, `failed`) |
| `batch_analyses_total` | Counter | `status` | Batch analysis completions |
| `ai_provider_requests_total` | Counter | `provider`, `status` | Outbound AI provider requests and responses |
| `ai_provider_latency_seconds` | Histogram | `provider` | Round-trip latency for LLM inferences |

---

## 4. Grafana Dashboards

Pre-configured provisioning dashboards are located in `monitoring/grafana/dashboards/`:
1. **API Health and Latency (`api_health_latency.json`):** Request throughput, p50/p95/p99 latency graphs, 5xx error percentage.
2. **Celery Workers and Queue Health (`celery_workers.json`):** Tasks per second, worker failures, execution duration.
3. **Database Health (`database_health.json`):** Connection pool saturation gauge, active leases vs idle connections.
4. **Business Operations & AI Metrics (`business_metrics.json`):** Resume analysis throughput, AI provider latency per model/vendor.

---

## 5. Health Check Endpoints

| Endpoint | Purpose | Target Consumer | Failure Action |
| :--- | :--- | :--- | :--- |
| `GET /health/liveness` | Process liveness probe | Docker / Kubernetes | Restart container if unresponsive |
| `GET /health/readiness` | Traffic readiness probe | Reverse Proxy / Load Balancer | Remove instance from active routing |
| `GET /health` | Legacy liveness alias | Backward compatibility | Same as `/health/liveness` |

### 5.1 Readiness Probe Response Format
```json
// HTTP 200 OK
{
  "status": "ready",
  "checks": {
    "database": "ok",
    "broker": "ok",
    "storage": "ok"
  }
}
```
If PostgreSQL or Redis is unreachable, `/health/readiness` returns HTTP 503 with `"status": "unready"`.

---

## 6. Structured JSON Logging

### 6.1 Format
When `LOG_FORMAT=json` or `DEBUG=false`, logs are emitted as single-line JSON:
```json
{
  "timestamp": "2026-11-20T11:35:00.123456Z",
  "level": "INFO",
  "logger": "app.routers.auth",
  "service": "resume-analyzer-api",
  "environment": "production",
  "request_id": "8f3b9c71a2e44d21",
  "message": "User authenticated successfully"
}
```

### 6.2 Log Masking Rules
`app/core/logging_config.py` enforces regex-based credential masking:
- `Bearer <token>` -> `Bearer [REDACTED_TOKEN]`
- `password="<val>"` -> `password="[REDACTED]"`
- `api_key="<val>"` -> `api_key="[REDACTED]"`
- `secret="<val>"` -> `secret="[REDACTED]"`

---

## 7. Recommended Production Alerts

| Alert | Condition | Severity | Recovery Action |
| :--- | :--- | :--- | :--- |
| **APIInstanceDown** | `up == 0` for 1m | `CRITICAL` | Check Docker container status, restart API container |
| **HighHTTP5xxErrorRate** | `5xx % > 5%` for 2m | `CRITICAL` | Inspect Sentry and API error logs, check DB connectivity |
| **HighRequestLatency** | `p95 > 2.0s` for 3m | `WARNING` | Check slow queries in PostgreSQL, scale Celery workers |
| **DatabasePoolSaturation** | `Pool usage > 85%` for 2m | `WARNING` | Increase pool size or investigate connection leaks |
| **HighCeleryTaskFailures** | `Failures > 0.5/s` for 3m | `WARNING` | Check worker logs, inspect Redis broker connectivity |
| **AIProviderErrorRate** | `AI errors > 0.2/s` for 3m | `WARNING` | Check upstream provider status (OpenRouter, Groq, Gemini) |
| **BackupFailure** | Last backup > 25h | `CRITICAL` | Inspect backup cron logs and disk space |
