"""Free tier: a few AI CV checks per day on the platform provider."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import settings
from app.models.ai_analysis_run import AIAnalysisRun
from app.models.application import Application, AnalysisStatus
from app.schemas.application_analysis import ApplicationAnalysis
from app.services.ai import provider as service
from tests.test_ai_provider import URL, _save
from tests.test_auto_analyze_filters import ANALYSIS


@pytest.fixture(autouse=True)
def free_tier(monkeypatch):
    monkeypatch.setattr(settings, "REQUIRE_USER_AI_CONFIG", False)
    monkeypatch.setattr(settings, "PLATFORM_AI_DAILY_CV_LIMIT", 2)


def _add_runs(db_session, user_id, n, *, source="default", status="completed", kind="application", when=None):
    for _ in range(n):
        run = AIAnalysisRun(kind=kind, status=status, owner_id=user_id, source=source)
        if when is not None:
            run.created_at = when
        db_session.add(run)
    db_session.commit()


def _analyze(client, application):
    with patch(
        "app.services.application_analysis.analyze_application", new_callable=AsyncMock
    ) as analyze:
        analyze.return_value = ApplicationAnalysis(**ANALYSIS)
        response = client.post(
            f"/api/applications/{application['id']}/analyze", headers=application["headers"]
        )
    return response, analyze


class TestCounting:
    def test_only_todays_successful_platform_cv_checks_count(self, db_session, user):
        uid = user["id"]
        _add_runs(db_session, uid, 1)
        _add_runs(db_session, uid, 1, status="failed")
        _add_runs(db_session, uid, 1, source="custom")
        _add_runs(db_session, uid, 1, kind="vacancy")
        _add_runs(db_session, uid, 1, when=datetime.now(timezone.utc) - timedelta(days=2))

        assert service.cv_checks_used_today(db_session, uid) == 1

    def test_remaining(self, db_session, user):
        cfg = service.resolve_for_user(db_session, user["id"])
        assert service.remaining_cv_checks(db_session, user["id"], cfg) == 2
        _add_runs(db_session, user["id"], 5)
        assert service.remaining_cv_checks(db_session, user["id"], cfg) == 0

    def test_custom_provider_is_unlimited(self, client, db_session, user):
        _save(client, user["headers"])
        _add_runs(db_session, user["id"], 5)
        cfg = service.resolve_for_user(db_session, user["id"])

        assert service.remaining_cv_checks(db_session, user["id"], cfg) is None
        service.ensure_cv_quota(db_session, user["id"], cfg)  # does not raise

    def test_zero_means_unlimited(self, monkeypatch, db_session, user):
        monkeypatch.setattr(settings, "PLATFORM_AI_DAILY_CV_LIMIT", 0)
        _add_runs(db_session, user["id"], 50)
        cfg = service.resolve_for_user(db_session, user["id"])

        assert service.remaining_cv_checks(db_session, user["id"], cfg) is None


class TestEnforcement:
    def test_manual_analysis_refused_when_limit_reached(self, client, db_session, sample_application, user):
        _add_runs(db_session, user["id"], 2)

        response, analyze = _analyze(client, sample_application)

        assert response.status_code == 429
        assert "free AI CV checks" in response.json()["detail"]
        assert analyze.await_count == 0
        db_session.expire_all()
        app = db_session.get(Application, sample_application["id"])
        assert app.analysis_status != AnalysisStatus.ANALYZING

    def test_manual_analysis_allowed_under_limit(self, client, db_session, sample_application, user):
        _add_runs(db_session, user["id"], 1)

        response, analyze = _analyze(client, sample_application)

        assert response.status_code == 200, response.text
        assert analyze.await_count == 1

    def test_background_run_marks_failed_with_reason(self, db_session, sample_application, user):
        import asyncio

        from app.services import application_analysis

        _add_runs(db_session, user["id"], 2)
        app = db_session.get(Application, sample_application["id"])
        with patch(
            "app.services.application_analysis.analyze_application", new_callable=AsyncMock
        ) as analyze:
            with pytest.raises(service.AIDailyLimitError):
                asyncio.run(application_analysis.run_analysis(db_session, app))

        assert analyze.await_count == 0
        assert app.analysis_status == AnalysisStatus.FAILED
        assert "free AI CV checks" in app.analysis_error

    def test_vacancy_analysis_is_not_limited(self, client, db_session, user):
        _add_runs(db_session, user["id"], 5)
        with patch("app.routers.jobs.analyze_vacancy", new_callable=AsyncMock) as analyze:
            analyze.return_value = {
                "company_name": "Acme",
                "position": "Dev",
                "description": "",
                "required_skills": "",
                "required_experience": "",
            }
            response = client.post(
                "/api/jobs/analyze", json={"content": "Acme hires a dev"}, headers=user["headers"]
            )

        assert response.status_code == 200, response.text

    def test_auto_analyze_refused_when_limit_reached(self, client, db_session, sample_application, user):
        _add_runs(db_session, user["id"], 2)

        response = client.post(
            "/api/applications/auto-analyze",
            json={"count": 5, "order": "oldest"},
            headers=user["headers"],
        )

        assert response.status_code == 429


    def test_auto_analyze_selects_only_remaining_checks(self, client, db_session, user):
        from app.models.job import Job

        job = Job(owner_id=user["id"], company_name="Acme", position="Dev")
        db_session.add(job)
        db_session.commit()
        for i in range(4):
            db_session.add(Application(job_id=job.id, name=f"A{i}", email=f"a{i}@example.com"))
        db_session.commit()
        _add_runs(db_session, user["id"], 1)  # 1 of 2 used

        response = client.post(
            "/api/applications/auto-analyze",
            json={"count": 4, "order": "oldest"},
            headers=user["headers"],
        )

        assert response.status_code == 201, response.text
        body = response.json()
        assert body["requested_count"] == 4
        assert body["selected_count"] == 1


class TestSettingsStatus:
    def test_shows_usage_on_platform_provider(self, client, db_session, user):
        _add_runs(db_session, user["id"], 1)

        body = client.get(URL, headers=user["headers"]).json()

        assert body["daily_cv_limit"] == 2
        assert body["cv_checks_used_today"] == 1

    def test_no_limit_with_own_provider(self, client, user):
        _save(client, user["headers"])

        body = client.get(URL, headers=user["headers"]).json()

        assert body["daily_cv_limit"] is None

    def test_no_limit_shown_when_own_provider_required(self, monkeypatch, client, user):
        monkeypatch.setattr(settings, "REQUIRE_USER_AI_CONFIG", True)

        body = client.get(URL, headers=user["headers"]).json()

        assert body["daily_cv_limit"] is None


def test_gemini_sends_api_key_in_goog_header():
    from app.services.ai.job_analyzer import _build_headers

    headers = _build_headers({"provider": "gemini", "api_key": "AIza-test"})

    assert headers["x-goog-api-key"] == "AIza-test"
    assert "Authorization" not in headers
