"""Tests for Phase 1 Observability & Monitoring: Sentry, Prometheus, Health Checks, Logging."""

from __future__ import annotations

import json
import logging
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.logging_config import JSONFormatter, scrub_log_message
from app.core.metrics import _normalize_path
from app.core.sentry import _before_send, init_sentry
from app.main import create_app


def test_health_liveness_endpoint():
    """Verify /health/liveness returns HTTP 200 without external dependencies."""
    app = create_app()
    client = TestClient(app)
    response = client.get("/health/liveness")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "api"

    # Backward compatibility: /health must also return 200
    legacy_resp = client.get("/health")
    assert legacy_resp.status_code == 200


def test_health_readiness_endpoint():
    """Verify /health/readiness checks database, broker, and storage."""
    app = create_app()
    client = TestClient(app)
    response = client.get("/health/readiness")
    assert response.status_code in (200, 503)
    data = response.json()
    assert "status" in data
    assert "checks" in data
    assert "database" in data["checks"]
    assert "broker" in data["checks"]
    assert "storage" in data["checks"]


def test_health_readiness_fails_gracefully_on_db_down():
    """Verify readiness returns HTTP 503 if database connectivity fails."""
    app = create_app()
    client = TestClient(app)
    with patch("app.core.database.engine.connect", side_effect=Exception("Connection refused")):
        response = client.get("/health/readiness")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unready"
        assert data["checks"]["database"] == "unhealthy"


def test_prometheus_metrics_endpoint():
    """Verify /metrics exposes standard Prometheus text exposition format."""
    app = create_app()
    client = TestClient(app)

    # Issue a normal request first so counters are incremented
    client.get("/health")

    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers.get("content-type", "")
    content = response.text
    assert "http_requests_total" in content
    assert "http_request_duration_seconds" in content
    assert "db_pool_size" in content
    assert "celery_task_events_total" in content


def test_metric_path_normalization():
    """Verify numeric IDs and UUIDs are masked to prevent Prometheus cardinality explosions."""
    assert _normalize_path("/api/applications/123/resume") == "/api/applications/{id}/resume"
    assert _normalize_path("/api/jobs/42") == "/api/jobs/{id}"
    assert _normalize_path("/api/interviews/a1b2c3d4e5f60718293a4b5c6d7e8f90") == "/api/interviews/{uuid}"


def test_sentry_data_scrubbing():
    """Verify Sentry before_send strips sensitive tokens, cookies, passwords, and resume text."""
    raw_event = {
        "request": {
            "headers": {
                "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.sensitive",
                "Cookie": "session_id=secret123; user=admin",
                "X-API-Key": "my-secret-key",
                "User-Agent": "Mozilla/5.0",
            },
            "data": {
                "email": "hr@example.com",
                "password": "SuperSecretPassword123!",
                "secret_key": "confidential_signing_key",
                "raw_resume": "Jane Doe, 10 years experience...",
            },
        },
        "extra": {
            "api_key": "sk-live-12345",
        },
    }

    sanitized = _before_send(raw_event, {})
    headers = sanitized["request"]["headers"]
    body = sanitized["request"]["data"]
    extra = sanitized["extra"]

    # Headers redacted
    assert headers["Authorization"] == "[REDACTED]"
    assert headers["Cookie"] == "[REDACTED]"
    assert headers["X-API-Key"] == "[REDACTED]"
    assert headers["User-Agent"] == "Mozilla/5.0"

    # Body redacted
    assert body["email"] == "hr@example.com"
    assert body["password"] == "[REDACTED]"
    assert body["secret_key"] == "[REDACTED]"
    assert body["raw_resume"] == "[REDACTED]"

    # Extra redacted
    assert extra["api_key"] == "[REDACTED]"


def test_sentry_disabled_gracefully_when_dsn_empty():
    """Verify init_sentry returns False and does not crash when SENTRY_DSN is empty."""
    with patch.object(settings, "SENTRY_DSN", ""):
        assert init_sentry() is False


def test_structured_json_logging_and_secret_masking():
    """Verify structured JSON formatter scrubs tokens and emits valid JSON."""
    formatter = JSONFormatter(service_name="test-api")
    record = logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg='User login attempt for admin with password="SecretPassword123" and Bearer abc.def.ghi',
        args=(),
        exc_info=None,
    )
    setattr(record, "request_id", "req-12345")

    formatted = formatter.format(record)
    log_json = json.loads(formatted)

    assert log_json["service"] == "test-api"
    assert log_json["request_id"] == "req-12345"
    assert log_json["level"] == "INFO"
    # Secrets masked
    assert "SecretPassword123" not in log_json["message"]
    assert "[REDACTED]" in log_json["message"]
    assert "abc.def.ghi" not in log_json["message"]
    assert "[REDACTED_TOKEN]" in log_json["message"]


def test_scrub_log_message_standalone():
    """Verify standalone log scrubbing function."""
    assert scrub_log_message('Bearer secret_jwt_token_here') == 'Bearer [REDACTED_TOKEN]'
    assert scrub_log_message('password="mysecret"') == 'password="[REDACTED]"'
    assert scrub_log_message('api_key="sk-live-123"') == 'api_key="[REDACTED]"'
