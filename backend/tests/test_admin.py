"""Tests for the superuser-only admin API (``/api/admin``).

Covers the security boundary (401/403/200 on every endpoint), the platform
wide listings and details, dashboard/analytics aggregation, runtime settings
and system health.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import settings
from app.models import User
from app.schemas.application_analysis import ApplicationAnalysis
from app.services.admin import health as system_health
from tests.payloads import INTERVIEW_PAYLOAD, JOB_PAYLOAD, APPLICATION_PAYLOAD

ADMIN_GET_ENDPOINTS = [
    "/api/admin/dashboard",
    "/api/admin/analytics",
    "/api/admin/filters",
    "/api/admin/users",
    "/api/admin/jobs",
    "/api/admin/applications",
    "/api/admin/candidates",
    "/api/admin/interviews",
    "/api/admin/ai-analysis",
    "/api/admin/ai-analysis/runs",
    "/api/admin/audit-logs",
    "/api/admin/audit-logs/meta",
    "/api/admin/system-errors",
    "/api/admin/settings",
    "/api/admin/system-health",
]


def _analysis(score: float) -> ApplicationAnalysis:
    return ApplicationAnalysis(match_percentage=score, summary="ok", ai_recommendation="hire")


def _create_job(client, headers, **overrides):
    response = client.post("/api/jobs", json={**JOB_PAYLOAD, **overrides}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def _create_application(client, headers, job_id, **overrides):
    response = client.post(
        f"/api/applications?job_id={job_id}", json={**APPLICATION_PAYLOAD, **overrides}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


def _analyze(client, headers, application_id, score):
    with patch(
        "app.services.application_analysis.analyze_application", new_callable=AsyncMock
    ) as mock_analyze:
        mock_analyze.return_value = _analysis(score)
        response = client.post(f"/api/applications/{application_id}/analyze", headers=headers)
    assert response.status_code == 200, response.text


@pytest.fixture
def platform(client, user, other_user):
    """Two HR users with jobs, applications, a candidate and an interview."""
    job_a = _create_job(client, user["headers"], company_name="Acme Corp", position="Backend Dev")
    job_b = _create_job(client, other_user["headers"], company_name="Globex", position="Designer")
    w1 = _create_application(client, user["headers"], job_a["id"], name="Alice", email="alice@x.com")
    w2 = _create_application(client, user["headers"], job_a["id"], name="Bob", email="bob@x.com")
    w3 = _create_application(client, other_user["headers"], job_b["id"], name="Carol", email="carol@x.com")
    _analyze(client, user["headers"], w1["id"], 85)
    client.post(f"/api/applications/{w1['id']}/convert-to-candidate", headers=user["headers"])
    interview = client.post(
        "/api/interviews",
        json={**INTERVIEW_PAYLOAD, "candidate_id": w1["id"]},
        headers=user["headers"],
    )
    assert interview.status_code == 201, interview.text
    return {"job_a": job_a, "job_b": job_b, "applications": [w1, w2, w3], "user": user, "other": other_user}


# ---------------------------------------------------------------------------
# Security boundary
# ---------------------------------------------------------------------------


class TestAuthorization:
    @pytest.mark.parametrize("path", ADMIN_GET_ENDPOINTS)
    def test_anonymous_gets_401(self, client, path):
        assert client.get(path).status_code == 401

    @pytest.mark.parametrize("path", ADMIN_GET_ENDPOINTS)
    def test_regular_hr_user_gets_403(self, client, user, path):
        response = client.get(path, headers=user["headers"])
        assert response.status_code == 403
        assert response.json()["detail"] == "Admin privileges required"

    @pytest.mark.parametrize("path", ADMIN_GET_ENDPOINTS)
    def test_admin_gets_200(self, client, admin, path):
        assert client.get(path, headers=admin["headers"]).status_code == 200

    def test_hr_user_cannot_mutate(self, client, user, sample_job):
        headers = user["headers"]
        assert client.delete(f"/api/admin/jobs/{sample_job['id']}", headers=headers).status_code == 403
        assert (
            client.patch(
                "/api/admin/settings", json={"registration_enabled": False}, headers=headers
            ).status_code
            == 403
        )
        # The job is untouched.
        assert client.get(f"/api/jobs/{sample_job['id']}", headers=headers).status_code == 200

    def test_demoted_admin_loses_access_immediately(self, client, admin, db_session):
        from app.crud import user as user_crud

        target = user_crud.get_user_by_id(db_session, admin["id"])
        user_crud.update_user(db_session, target, {"is_superuser": False})
        assert client.get("/api/admin/dashboard", headers=admin["headers"]).status_code == 403

    def test_hr_endpoints_stay_owner_scoped(self, client, platform):
        """Admin data never leaks through the normal HR endpoints."""
        other_job = platform["job_b"]["id"]
        headers = platform["user"]["headers"]
        assert client.get(f"/api/jobs/{other_job}", headers=headers).status_code == 404
        names = {w["name"] for w in client.get("/api/applications", headers=headers).json()}
        assert "Carol" not in names

    def test_profile_reports_role(self, client, admin, user):
        assert client.get("/api/auth/me", headers=admin["headers"]).json()["is_superuser"] is True
        assert client.get("/api/auth/me", headers=user["headers"]).json()["is_superuser"] is False


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


class TestAdminUsers:
    def test_lists_users_with_counts_and_no_secrets(self, client, admin, platform):
        response = client.get("/api/admin/users?sort=email&order=asc", headers=admin["headers"])
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 3
        rows = {row["email"]: row for row in body["items"]}
        assert rows["hr@example.com"]["jobs_count"] == 1
        assert rows["hr@example.com"]["applications_count"] == 2
        assert rows["other@example.com"]["applications_count"] == 1
        assert rows["admin@example.com"]["is_superuser"] is True
        text = response.text
        assert "hashed_password" not in text and "google_id" not in text

    def test_filters_search_and_pagination(self, client, admin, platform):
        headers = admin["headers"]
        admins = client.get("/api/admin/users?role=admin", headers=headers).json()
        assert [row["email"] for row in admins["items"]] == ["admin@example.com"]

        found = client.get("/api/admin/users?q=OTHER", headers=headers).json()
        assert [row["email"] for row in found["items"]] == ["other@example.com"]

        page = client.get("/api/admin/users?limit=2&page=2&sort=email&order=asc", headers=headers).json()
        assert page["total"] == 3 and len(page["items"]) == 1 and page["page"] == 2

    def test_search_wildcards_are_literal(self, client, admin, platform):
        response = client.get("/api/admin/users?q=%25", headers=admin["headers"])
        assert response.json()["total"] == 0

    def test_status_filter_after_deactivation(self, client, admin, platform):
        user_id = platform["other"]["id"]
        assert client.put(
            f"/api/users/{user_id}", json={"is_active": False}, headers=admin["headers"]
        ).status_code == 200
        inactive = client.get("/api/admin/users?status=inactive", headers=admin["headers"]).json()
        assert [row["id"] for row in inactive["items"]] == [user_id]
        # Deactivation takes effect on the very next request.
        assert client.get("/api/jobs", headers=platform["other"]["headers"]).status_code == 401

    def test_rejects_invalid_parameters(self, client, admin):
        headers = admin["headers"]
        assert client.get("/api/admin/users?limit=101", headers=headers).status_code == 422
        assert client.get("/api/admin/users?sort=hashed_password", headers=headers).status_code == 422
        assert client.get("/api/admin/users?page=0", headers=headers).status_code == 422
        assert client.get(
            "/api/admin/users?date_from=2026-02-01&date_to=2026-01-01", headers=headers
        ).status_code == 422

    def test_user_detail(self, client, admin, platform):
        user_id = platform["user"]["id"]
        response = client.get(f"/api/admin/users/{user_id}", headers=admin["headers"])
        assert response.status_code == 200
        body = response.json()
        assert body["stats"] == {
            "jobs": 1,
            "applications": 2,
            "candidates": 1,
            "interviews": 1,
            "ai_analyses": 1,
            "ai_runs_failed": 0,
        }
        assert body["ai_provider_source"] == "default"
        assert len(body["recent_jobs"]) == 1 and len(body["recent_applications"]) == 2
        actions = {entry["action"] for entry in body["recent_activity"]}
        assert {"CREATE_JOB", "CREATE_INTERVIEW"} <= actions
        assert body["last_login_at"] is not None  # set by registration

    def test_user_detail_404(self, client, admin):
        assert client.get("/api/admin/users/999999", headers=admin["headers"]).status_code == 404


class TestUserMutationsAreAudited:
    def _actions(self, client, admin, resource_id):
        logs = client.get(
            f"/api/admin/audit-logs?resource_type=user&q={resource_id}", headers=admin["headers"]
        ).json()["items"]
        return [entry["action"] for entry in logs if entry["resource_id"] == str(resource_id)]

    def test_activate_deactivate_promote_demote(self, client, admin, user):
        uid, headers = user["id"], admin["headers"]
        client.put(f"/api/users/{uid}", json={"is_active": False, "is_superuser": True}, headers=headers)
        client.put(f"/api/users/{uid}", json={"is_active": True, "is_superuser": False}, headers=headers)
        actions = self._actions(client, admin, uid)
        for expected in ("DEACTIVATE_USER", "PROMOTE_USER", "ACTIVATE_USER", "DEMOTE_USER"):
            assert expected in actions

    def test_no_op_update_is_not_audited(self, client, admin, user):
        client.put(f"/api/users/{user['id']}", json={"is_active": True}, headers=admin["headers"])
        assert "ACTIVATE_USER" not in self._actions(client, admin, user["id"])

    def test_delete_is_audited_with_snapshot(self, client, admin, user):
        assert client.delete(f"/api/users/{user['id']}", headers=admin["headers"]).status_code == 204
        logs = client.get("/api/admin/audit-logs?action=DELETE_USER", headers=admin["headers"]).json()
        entry = logs["items"][0]
        assert entry["details"]["target_email"] == "hr@example.com"
        assert entry["actor_email"] == "admin@example.com"

    def test_self_protection_still_applies(self, client, admin):
        headers = admin["headers"]
        assert client.put(
            f"/api/users/{admin['id']}", json={"is_superuser": False}, headers=headers
        ).status_code == 400
        assert client.delete(f"/api/users/{admin['id']}", headers=headers).status_code == 400

    def test_blank_name_rejected(self, client, admin, user):
        response = client.put(f"/api/users/{user['id']}", json={"full_name": "   "}, headers=admin["headers"])
        assert response.status_code == 422

    def test_last_active_admin_is_protected(self, db_session, admin):
        """Service-level safeguard: the only active admin cannot be removed."""
        from app.crud import user as user_crud
        from app.schemas.user import UserCreate
        from app.services.admin import users as user_admin

        other_admin = user_crud.create_user(
            db_session, UserCreate(email="second@example.com", full_name="Second", password="Pass12345"),
            is_superuser=True,
        )
        first = user_crud.get_user_by_id(db_session, admin["id"])
        # Deactivate the first admin while two exist: allowed.
        user_admin.update_user(db_session, other_admin, first, {"is_active": False})
        # Now `other_admin` is the only active admin; a (hypothetical) inactive
        # superuser acting on it must not remove the last administrator.
        with pytest.raises(user_admin.UserAdminError):
            user_admin.update_user(db_session, first, other_admin, {"is_superuser": False})


# ---------------------------------------------------------------------------
# Dashboard + analytics
# ---------------------------------------------------------------------------


class TestDashboard:
    def test_empty_platform(self, client, admin):
        body = client.get("/api/admin/dashboard", headers=admin["headers"]).json()
        kpis = body["kpis"]
        assert kpis["users_total"] == 1 and kpis["admins"] == 1
        assert kpis["jobs"] == kpis["applications"] == kpis["interviews"] == 0
        assert len(body["trend"]) == 30
        assert all(point["jobs"] == 0 for point in body["trend"])

    def test_aggregates_whole_platform(self, client, admin, platform):
        body = client.get("/api/admin/dashboard", headers=admin["headers"]).json()
        kpis = body["kpis"]
        assert kpis["users_total"] == 3
        assert kpis["users_active"] == 3 and kpis["users_inactive"] == 0
        assert kpis["jobs"] == 2
        assert kpis["applications"] == 3
        assert kpis["candidates"] == 1
        assert kpis["interviews"] == 1
        assert kpis["ai_analyzed"] == 1
        today = body["trend"][-1]
        assert today["jobs"] == 2 and today["applications"] == 3 and today["registrations"] == 3
        assert today["ai_completed"] == 1

    def test_recent_activity_skips_sign_ins(self, client, admin, platform):
        body = client.get("/api/admin/dashboard", headers=admin["headers"]).json()
        actions = [entry["action"] for entry in body["recent_activity"]]
        assert "CREATE_JOB" in actions and "AI_ANALYSIS_COMPLETED" in actions
        assert "LOGIN" not in actions


class TestAnalytics:
    @pytest.mark.parametrize(
        ("range_", "buckets", "bucket"),
        [("7d", 7, "day"), ("30d", 30, "day"), ("90d", 13, "week"), ("12m", 12, "month")],
    )
    def test_ranges(self, client, admin, platform, range_, buckets, bucket):
        body = client.get(f"/api/admin/analytics?range={range_}", headers=admin["headers"]).json()
        assert body["bucket"] == bucket
        assert len(body["series"]) == buckets
        assert body["totals"]["jobs"] == 2
        assert body["totals"]["applications"] == 3

    def test_distributions(self, client, admin, platform):
        body = client.get("/api/admin/analytics", headers=admin["headers"]).json()
        status = {item["key"]: item["count"] for item in body["application_status"]}
        assert status["new"] == 3
        analysis = {item["key"]: item["count"] for item in body["analysis_status"]}
        assert analysis["completed"] == 1
        scores = {item["key"]: item["count"] for item in body["score_distribution"]}
        assert scores["80-89"] == 1
        assert body["avg_ai_score"] == 85.0
        assert body["avg_applications_per_job"] == 1.5
        assert body["top_jobs"][0]["applications"] == 2
        companies = {row["company"] for row in body["top_companies"]}
        assert companies == {"Acme Corp", "Globex"}

    def test_invalid_range(self, client, admin):
        assert client.get("/api/admin/analytics?range=5y", headers=admin["headers"]).status_code == 422


# ---------------------------------------------------------------------------
# Jobs, applications, candidates, interviews
# ---------------------------------------------------------------------------


class TestAdminJobs:
    def test_lists_all_owners_jobs(self, client, admin, platform):
        body = client.get("/api/admin/jobs?sort=applications&order=desc", headers=admin["headers"]).json()
        assert body["total"] == 2
        first = body["items"][0]
        assert first["company_name"] == "Acme Corp"
        assert first["applications_count"] == 2
        assert first["candidates_count"] == 1
        assert first["analyzed_count"] == 1
        assert first["owner_email"] == "hr@example.com"

    def test_filters(self, client, admin, platform):
        headers = admin["headers"]
        owner = platform["other"]["id"]
        by_owner = client.get(f"/api/admin/jobs?owner_id={owner}", headers=headers).json()
        assert [row["company_name"] for row in by_owner["items"]] == ["Globex"]
        by_company = client.get("/api/admin/jobs?company=Acme%20Corp", headers=headers).json()
        assert by_company["total"] == 1
        by_search = client.get("/api/admin/jobs?q=design", headers=headers).json()
        assert by_search["total"] == 1
        paged = client.get("/api/admin/jobs?limit=1&page=2", headers=headers).json()
        assert paged["total"] == 2 and len(paged["items"]) == 1

    def test_detail(self, client, admin, platform):
        job_id = platform["job_a"]["id"]
        body = client.get(f"/api/admin/jobs/{job_id}", headers=admin["headers"]).json()
        assert body["description"] == JOB_PAYLOAD["description"]
        assert {"key": "new", "count": 2} in body["status_breakdown"]
        assert client.get("/api/admin/jobs/999999", headers=admin["headers"]).status_code == 404

    def test_admin_delete_is_audited(self, client, admin, platform):
        job_id = platform["job_b"]["id"]
        assert client.delete(f"/api/admin/jobs/{job_id}", headers=admin["headers"]).status_code == 204
        assert client.get(f"/api/admin/jobs/{job_id}", headers=admin["headers"]).status_code == 404
        logs = client.get("/api/admin/audit-logs?action=DELETE_JOB", headers=admin["headers"]).json()
        entry = logs["items"][0]
        assert entry["resource_id"] == str(job_id)
        assert entry["details"]["by_admin"] is True
        assert entry["details"]["owner_id"] == platform["other"]["id"]
        assert client.delete(f"/api/admin/jobs/{job_id}", headers=admin["headers"]).status_code == 404

    def test_filter_options(self, client, admin, platform):
        body = client.get("/api/admin/filters", headers=admin["headers"]).json()
        assert {owner["email"] for owner in body["owners"]} == {"hr@example.com", "other@example.com"}
        assert body["companies"] == ["Acme Corp", "Globex"]


class TestAdminApplications:
    def test_list_and_summary(self, client, admin, platform):
        body = client.get("/api/admin/applications", headers=admin["headers"]).json()
        assert body["total"] == 3
        assert body["summary"]["total"] == 3
        assert body["summary"]["analysis_status"]["completed"] == 1
        alice = next(row for row in body["items"] if row["name"] == "Alice")
        assert alice["ai_score"] == 85 and alice["ai_recommendation"] == "hire"
        bob = next(row for row in body["items"] if row["name"] == "Bob")
        assert bob["ai_score"] is None  # never analysed: no fake 0 score
        assert "resume_path" not in body["items"][0]

    def test_filters(self, client, admin, platform):
        headers = admin["headers"]

        def names(query):
            response = client.get(f"/api/admin/applications?{query}", headers=headers)
            assert response.status_code == 200, response.text
            return sorted(row["name"] for row in response.json()["items"])

        assert names("analysis=analyzed") == ["Alice"]
        assert names("analysis=not_analyzed") == ["Bob", "Carol"]
        assert names("score_min=80&score_max=90") == ["Alice"]
        assert names("score_min=90") == []
        assert names(f"owner_id={platform['other']['id']}") == ["Carol"]
        assert names("company=Globex") == ["Carol"]
        assert names(f"job_id={platform['job_a']['id']}") == ["Alice", "Bob"]
        assert names("q=bob@x") == ["Bob"]
        assert names("application_status=rejected") == []
        assert names("sort=ai_score&order=desc")[0] in {"Alice", "Bob", "Carol"}

    def test_invalid_filters(self, client, admin):
        headers = admin["headers"]
        assert client.get("/api/admin/applications?score_min=90&score_max=10", headers=headers).status_code == 422
        assert client.get("/api/admin/applications?analysis=maybe", headers=headers).status_code == 422
        assert client.get("/api/admin/applications?score_min=101", headers=headers).status_code == 422

    def test_candidates_only(self, client, admin, platform):
        body = client.get("/api/admin/candidates", headers=admin["headers"]).json()
        assert [row["name"] for row in body["items"]] == ["Alice"]
        assert body["summary"]["total"] == 1
        filtered = client.get("/api/admin/candidates?hiring_status=do_not_hire", headers=admin["headers"])
        assert filtered.json()["total"] == 0

    def test_detail_is_read_only_and_safe(self, client, admin, platform):
        application_id = platform["applications"][0]["id"]
        body = client.get(f"/api/admin/applications/{application_id}", headers=admin["headers"]).json()
        assert body["analysis"]["match_percentage"] == 85
        assert body["hiring_status"] == "hire"  # human decision, untouched by the AI
        assert body["has_resume"] is True
        assert "resume_path" not in body and "resume_url" not in body
        assert len(body["interviews"]) == 1
        assert client.get("/api/admin/applications/999999", headers=admin["headers"]).status_code == 404


class TestAdminInterviews:
    def test_list_and_summary(self, client, admin, platform):
        body = client.get("/api/admin/interviews", headers=admin["headers"]).json()
        assert body["total"] == 1
        row = body["items"][0]
        assert row["candidate_name"] == "Alice" and row["hr_email"] == "hr@example.com"
        summary = body["summary"]
        assert summary["total"] == 1
        # INTERVIEW_PAYLOAD is scheduled in the past and still "upcoming".
        assert summary["upcoming"] + summary["overdue"] == 1
        assert summary["candidate_progress"]["not_completed"] == 1

    def test_filters(self, client, admin, platform):
        headers = admin["headers"]
        assert client.get("/api/admin/interviews?status=completed", headers=headers).json()["total"] == 0
        assert client.get("/api/admin/interviews?company=Globex", headers=headers).json()["total"] == 0
        assert client.get("/api/admin/interviews?q=anna", headers=headers).json()["total"] == 1


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


class TestAdminSettings:
    def test_never_returns_secrets(self, client, admin, monkeypatch):
        monkeypatch.setattr(settings, "RESEND_API_KEY", "re_TopSecretValue123")
        monkeypatch.setattr(settings, "AI_API_KEY", "sk-or-TopSecretValue456")
        response = client.get("/api/admin/settings", headers=admin["headers"])
        assert response.status_code == 200
        assert "TopSecretValue" not in response.text
        assert settings.SECRET_KEY not in response.text
        config = response.json()["configuration"]
        assert config["email"]["configured"] is True
        assert config["ai"]["api_key_configured"] is True

    def test_registration_switch(self, client, admin, user_factory):
        headers = admin["headers"]
        response = client.patch("/api/admin/settings", json={"registration_enabled": False}, headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["runtime"]["registration_enabled"] is False
        assert body["runtime"]["updated_by_email"] == "admin@example.com"

        blocked = user_factory(email="late@example.com")
        assert blocked.status_code == 403
        assert "disabled" in blocked.json()["detail"]

        logs = client.get("/api/admin/audit-logs?action=UPDATE_SETTINGS", headers=headers).json()
        assert logs["items"][0]["details"] == {
            "registration_enabled_from": True,
            "registration_enabled_to": False,
        }

        client.patch("/api/admin/settings", json={"registration_enabled": True}, headers=headers)
        assert user_factory(email="late@example.com").status_code == 201

    def test_unknown_fields_rejected(self, client, admin):
        response = client.patch(
            "/api/admin/settings", json={"SECRET_KEY": "x"}, headers=admin["headers"]
        )
        assert response.status_code == 422

    @pytest.mark.anyio
    async def test_first_google_sign_in_obeys_switch(self, db_session, admin, monkeypatch):
        from app.services import auth as auth_service
        from app.services import platform_settings as platform_settings_service
        from app.services.google_auth import GoogleUserProfile

        async def fake_authenticate(code, redirect_uri=None):  # noqa: ARG001
            return GoogleUserProfile(
                google_id="g-123", email="new-google@example.com", full_name="New", picture=None
            )

        monkeypatch.setattr(auth_service, "authenticate_with_google", fake_authenticate)
        admin_user = db_session.get(User, admin["id"])
        platform_settings_service.update_settings(db_session, admin_user, {"registration_enabled": False})
        with pytest.raises(auth_service.RegistrationDisabledError):
            await auth_service.login_with_google(db_session, "code")


# ---------------------------------------------------------------------------
# System health
# ---------------------------------------------------------------------------


class TestSystemHealth:
    def test_healthy_database(self, client, admin):
        body = client.get("/api/admin/system-health", headers=admin["headers"]).json()
        components = {component["key"]: component for component in body["components"]}
        assert set(components) == {"api", "database", "ai_provider", "email", "storage", "workers"}
        assert components["database"]["status"] == "healthy"
        assert components["database"]["latency_ms"] is not None
        assert components["storage"]["status"] == "healthy"

    def test_database_failure_is_reported_safely(self, client, admin, monkeypatch):
        def broken(db):  # noqa: ARG001
            raise RuntimeError(f"could not connect to {settings.DATABASE_URL}")

        monkeypatch.setattr(system_health, "_ping_database", broken)
        response = client.get("/api/admin/system-health", headers=admin["headers"])
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "down"
        database = next(c for c in body["components"] if c["key"] == "database")
        assert database["status"] == "down"
        assert settings.DATABASE_URL not in response.text
        assert "postgres:" not in response.text

    def test_ai_provider_status_without_leaking_key(self, client, admin, monkeypatch):
        monkeypatch.setattr(settings, "AI_API_KEY", "")
        monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "")
        body = client.get("/api/admin/system-health", headers=admin["headers"]).json()
        ai = next(c for c in body["components"] if c["key"] == "ai_provider")
        assert ai["status"] == "not_configured"

        monkeypatch.setattr(settings, "AI_API_KEY", "sk-or-VerySecretKey99999")
        monkeypatch.setattr(settings, "AI_MODEL", "test/model")
        response = client.get("/api/admin/system-health", headers=admin["headers"])
        ai = next(c for c in response.json()["components"] if c["key"] == "ai_provider")
        # Configured but unverified: no attempt has succeeded in the last hour.
        assert ai["status"] == "configured"
        assert "VerySecretKey" not in response.text
