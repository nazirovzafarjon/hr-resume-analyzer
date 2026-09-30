"""Tests for the audit trail, system error recording and AI run monitoring."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import create_app
from app.schemas.application_analysis import ApplicationAnalysis
from app.services import audit
from app.services.admin import errors as error_monitor
from app.services.ai.job_analyzer import AIProviderUnavailableError, AIRateLimitError
from tests.conftest import TEST_USER_PASSWORD


def _logs(client, admin, **params):
    response = client.get("/api/admin/audit-logs", params=params, headers=admin["headers"])
    assert response.status_code == 200, response.text
    return response.json()


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------


class TestAuditTrail:
    def test_auth_events_are_logged_without_credentials(self, client, admin, user):
        login = client.post(
            "/api/auth/login", json={"email": user["email"], "password": TEST_USER_PASSWORD}
        )
        assert login.status_code == 200
        token = login.json()["access_token"]
        client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})

        body = _logs(client, admin, resource_type="user", limit=100)
        actions = [entry["action"] for entry in body["items"]]
        assert {"REGISTER", "LOGIN", "LOGOUT"} <= set(actions)
        login_entry = next(e for e in body["items"] if e["action"] == "LOGIN")
        assert login_entry["details"] == {"method": "password"}
        assert login_entry["actor_email"] == user["email"]
        assert login_entry["ip_address"]  # the test client's peer address

        raw = json.dumps(body)
        assert TEST_USER_PASSWORD not in raw
        assert token not in raw
        assert "hashed_password" not in raw

    def test_password_change_is_logged(self, client, admin, user):
        response = client.patch(
            "/api/auth/me/password",
            json={"current_password": TEST_USER_PASSWORD, "new_password": "BrandNewPass456"},
            headers=user["headers"],
        )
        assert response.status_code == 200
        body = _logs(client, admin, action="PASSWORD_CHANGE")
        assert body["total"] == 1
        assert "BrandNewPass456" not in json.dumps(body)

    def test_domain_events(self, client, admin, sample_application):
        headers = sample_application["headers"]
        client.patch(
            f"/api/applications/{sample_application['id']}",
            json={"application_status": "reviewing", "name": "Renamed"},
            headers=headers,
        )
        update = _logs(client, admin, action="UPDATE_APPLICATION")["items"][0]
        # Status values are recorded; free-text fields only by name.
        assert update["details"]["application_status"] == "reviewing"
        assert update["details"]["fields"] == ["application_status", "name"]
        assert "Renamed" not in json.dumps(update)

        client.delete(f"/api/applications/{sample_application['id']}", headers=headers)
        client.delete(f"/api/jobs/{sample_application['job_id']}", headers=headers)
        actions = {e["action"] for e in _logs(client, admin, limit=100)["items"]}
        assert {"CREATE_JOB", "CREATE_APPLICATION", "DELETE_APPLICATION", "DELETE_JOB"} <= actions

    def test_filters_and_pagination(self, client, admin, sample_job):
        headers = sample_job["headers"]
        for index in range(3):
            client.put(
                f"/api/jobs/{sample_job['id']}", json={"position": f"Role {index}"}, headers=headers
            )
        page = _logs(client, admin, action="UPDATE_JOB", limit=2, page=1)
        assert page["total"] == 3 and len(page["items"]) == 2
        # Newest first.
        assert page["items"][0]["id"] > page["items"][1]["id"]
        assert _logs(client, admin, q="UPDATE_J")["total"] == 3
        assert _logs(client, admin, actor_id=sample_job["owner_id"], action="CREATE_JOB")["total"] == 1
        assert _logs(client, admin, date_from="2000-01-01", date_to="2000-01-02")["total"] == 0

    def test_meta_lists_known_values(self, client, admin):
        meta = client.get("/api/admin/audit-logs/meta", headers=admin["headers"]).json()
        assert "DELETE_USER" in meta["actions"] and "UPDATE_SETTINGS" in meta["actions"]
        assert "user" in meta["resource_types"]

    def test_audit_log_is_read_only(self, client, admin):
        headers = admin["headers"]
        assert client.delete("/api/admin/audit-logs", headers=headers).status_code == 405
        assert client.put("/api/admin/audit-logs", json={}, headers=headers).status_code == 405

    def test_public_application_has_no_actor_or_ip(self, client, admin, sample_job):
        from app.services.audit import AuditAction, AuditResource

        # The legacy public apply endpoint (multipart resume upload).
        response = client.post(
            f"/api/public/apply/{sample_job['data']['public_id']}",
            data={"name": "Anon", "email": "anon@example.com"},
            files={"resume": ("cv.txt", b"hello", "text/plain")},
        )
        assert response.status_code == 201, response.text
        entry = _logs(client, admin, action=AuditAction.APPLICATION_RECEIVED)["items"][0]
        assert entry["resource_type"] == AuditResource.APPLICATION
        assert entry["actor_user_id"] is None and entry["ip_address"] is None


class TestSanitizeDetails:
    def test_drops_sensitive_keys_and_nesting(self):
        cleaned = audit.sanitize_details(
            {
                "password": "x",
                "new_password": "y",
                "access_token": "z",
                "api_key": "k",
                "Authorization": "Bearer abc",
                "resume_text": "cv",
                "payload": {"password": "nested"},
                "fields": ["name", "email"],
                "position": "Backend",
            }
        )
        assert cleaned == {"fields": ["name", "email"], "position": "Backend"}

    def test_truncates_long_values(self):
        cleaned = audit.sanitize_details({"note": "a" * 1000})
        assert len(cleaned["note"]) == 200

    def test_failure_never_raises(self, db_session, monkeypatch):
        from app.crud import audit_log as audit_crud

        def boom(*args, **kwargs):
            raise RuntimeError("db down")

        monkeypatch.setattr(audit_crud, "create_entry", boom)
        audit.record(db_session, "LOGIN", resource_type="user")  # must not raise


# ---------------------------------------------------------------------------
# System errors
# ---------------------------------------------------------------------------


@pytest.fixture
def exploding_client(_prepare_database, monkeypatch):
    """An app with an extra route that fails unexpectedly (production mode)."""
    monkeypatch.setattr(settings, "DEBUG", False)
    app = create_app()

    @app.get("/api/_test/explode")
    def explode():
        raise RuntimeError(f"boom while using {settings.DATABASE_URL} token=abc123")

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


class TestSystemErrors:
    def test_unhandled_error_is_recorded_safely(self, exploding_client, client, admin):
        response = exploding_client.get(
            "/api/_test/explode", headers={"X-Request-ID": "req-abc-12345"}
        )
        assert response.status_code == 500
        assert response.json() == {"detail": "Internal server error", "request_id": "req-abc-12345"}
        assert "boom" not in response.text  # nothing internal reaches the client

        body = client.get("/api/admin/system-errors", headers=admin["headers"]).json()
        assert body["total"] == 1
        row = body["items"][0]
        assert row["request_id"] == "req-abc-12345"
        assert row["status_code"] == 500 and row["error_type"] == "RuntimeError"
        assert row["path"] == "/api/_test/explode" and row["method"] == "GET"
        assert "postgres:postgres@" not in row["message"]
        assert "abc123" not in row["message"]
        assert body["summary"]["last_24h"] == 1

    def test_error_is_attributed_to_user(self, exploding_client, client, admin, user):
        exploding_client.get("/api/_test/explode", headers=user["headers"])
        row = client.get("/api/admin/system-errors", headers=admin["headers"]).json()["items"][0]
        assert row["user_id"] == user["id"] and row["user_email"] == user["email"]

    def test_upstream_5xx_is_recorded(self, client, admin, user):
        with patch("app.routers.jobs.analyze_vacancy", new_callable=AsyncMock) as mock_analyze:
            mock_analyze.side_effect = AIProviderUnavailableError()
            response = client.post(
                "/api/jobs/analyze", json={"content": "Senior Python developer"}, headers=user["headers"]
            )
        assert response.status_code == 503
        body = client.get("/api/admin/system-errors?status_code=503", headers=admin["headers"]).json()
        assert body["total"] == 1
        assert body["items"][0]["error_type"] == "HTTPException"

    def test_client_errors_are_not_recorded(self, client, admin, user):
        client.get("/api/jobs/999999", headers=user["headers"])  # 404
        assert client.get("/api/admin/system-errors", headers=admin["headers"]).json()["total"] == 0

    def test_filters_validate(self, client, admin):
        headers = admin["headers"]
        assert client.get("/api/admin/system-errors?status_code=404", headers=headers).status_code == 422
        assert client.get("/api/admin/system-errors?q=anything", headers=headers).status_code == 200

    def test_every_response_has_request_id(self, client):
        response = client.get("/health")
        assert len(response.headers["X-Request-ID"]) >= 8
        # A malicious incoming id is replaced, never echoed.
        response = client.get("/health", headers={"X-Request-ID": "bad id <script>injected"})
        assert "injected" not in response.headers["X-Request-ID"]

    def test_scrub(self):
        scrubbed = error_monitor.scrub(
            "postgresql://user:hunter2@db/app Bearer eyJhbGciOi.abc.def api_key=sk-live-1234567890abcdef"
        )
        assert "hunter2" not in scrubbed
        assert "eyJhbGciOi" not in scrubbed
        assert "sk-live-1234567890abcdef" not in scrubbed


# ---------------------------------------------------------------------------
# AI monitoring
# ---------------------------------------------------------------------------


class TestAIMonitoring:
    def _analyze(self, client, application, **mock_kwargs):
        with patch(
            "app.services.application_analysis.analyze_application", new_callable=AsyncMock
        ) as mock_analyze:
            for key, value in mock_kwargs.items():
                setattr(mock_analyze, key, value)
            return client.post(
                f"/api/applications/{application['id']}/analyze?force=true", headers=application["headers"]
            )

    def test_success_and_failure_are_recorded(self, client, admin, sample_application, monkeypatch):
        monkeypatch.setattr(settings, "AI_API_KEY", "sk-or-SuperSecretKey123456")
        self._analyze(client, sample_application, side_effect=AIRateLimitError())
        self._analyze(
            client,
            sample_application,
            return_value=ApplicationAnalysis(match_percentage=72, summary="ok"),
        )

        runs = client.get("/api/admin/ai-analysis/runs", headers=admin["headers"])
        assert runs.status_code == 200
        items = runs.json()["items"]
        assert [item["status"] for item in items] == ["completed", "failed"]
        completed, failed = items
        assert completed["score"] == 72 and completed["duration_ms"] is not None
        assert completed["kind"] == "application" and completed["source"] == "default"
        assert completed["provider"] == settings.AI_PROVIDER
        assert failed["error_category"] == "rate_limited"
        assert failed["http_status"] == 429
        assert failed["error_message"] == AIRateLimitError().message
        assert "SuperSecretKey" not in runs.text

        overview = client.get("/api/admin/ai-analysis", headers=admin["headers"])
        body = overview.json()
        assert body["runs_all_time"]["total"] == 2
        assert body["runs_all_time"]["success_rate"] == 50.0
        assert {"key": "rate_limited", "count": 1} in body["failure_categories"]
        assert "SuperSecretKey" not in overview.text

        failed_only = client.get("/api/admin/ai-analysis/runs?status=failed", headers=admin["headers"])
        assert failed_only.json()["total"] == 1

        # Both outcomes also appear in the audit trail.
        actions = {e["action"] for e in _logs(client, admin, resource_type="application")["items"]}
        assert {"AI_ANALYSIS_FAILED", "AI_ANALYSIS_COMPLETED"} <= actions

    def test_unexpected_error_is_recorded(self, client, admin, sample_application):
        with pytest.raises(RuntimeError):
            self._analyze(client, sample_application, side_effect=RuntimeError("provider exploded"))
        run = client.get("/api/admin/ai-analysis/runs", headers=admin["headers"]).json()["items"][0]
        assert run["error_category"] == "unexpected"
        assert "exploded" not in (run["error_message"] or "")

    def test_vacancy_validation_is_not_counted(self, client, admin, user):
        response = client.post("/api/jobs/analyze", json={"content": "   "}, headers=user["headers"])
        assert response.status_code == 422
        assert client.get("/api/admin/ai-analysis/runs", headers=admin["headers"]).json()["total"] == 0

    def test_unknown_category_rejected(self, client, admin):
        response = client.get(
            "/api/admin/ai-analysis/runs?error_category=nope", headers=admin["headers"]
        )
        assert response.status_code == 422

    def test_monitoring_failure_does_not_break_analysis(self, client, sample_application, monkeypatch):
        from app.crud import ai_analysis_run as run_crud

        def boom(*args, **kwargs):
            raise RuntimeError("monitoring down")

        monkeypatch.setattr(run_crud, "create_run", boom)
        response = self._analyze(
            client, sample_application, return_value=ApplicationAnalysis(match_percentage=60, summary="ok")
        )
        assert response.status_code == 200
        assert response.json()["analysis_status"] == "completed"
