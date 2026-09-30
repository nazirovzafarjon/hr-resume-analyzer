"""Auto Analyze: filters, ordering, eligibility and batch processing.

Selection is tested through the service and the HTTP endpoints; batch
processing calls ``run_batch_analysis`` directly (no background task) with the
AI call patched out.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.models.worker import AnalysisBatch, AnalysisStatus, ApplicationStatus, Worker
from app.schemas.application_analysis import ApplicationAnalysis
from app.services.ai import batch as service
from app.services.ai.job_analyzer import AIProviderUnavailableError
from tests.payloads import JOB_PAYLOAD, WORKER_PAYLOAD

ANALYSIS = {
    "match_percentage": 80,
    "matched_requirements": [],
    "missing_requirements": [],
    "matched_skills": ["Python"],
    "missing_skills": [],
    "strengths": [],
    "weaknesses": [],
    "risks": [],
    "experience_summary": "",
    "education_summary": "",
    "candidate_summary": "",
    "ai_recommendation": "hire",
    "recommendation_reason": "",
}


def _analysis() -> ApplicationAnalysis:
    return ApplicationAnalysis(**ANALYSIS)


@pytest.fixture
def make_job(client, user):
    def _make(company="Acme Corp", position="Backend Developer", headers=None):
        payload = {**JOB_PAYLOAD, "company_name": company, "position": position}
        response = client.post("/api/jobs", json=payload, headers=headers or user["headers"])
        assert response.status_code == 201, response.text
        return response.json()["id"]

    return _make


@pytest.fixture
def make_app(client, user, db_session):
    """Create an application with a controlled age and statuses."""

    def _make(
        job_id,
        *,
        minutes_ago=0,
        application_status=ApplicationStatus.NEW,
        analysis_status=AnalysisStatus.NEW,
        headers=None,
    ):
        response = client.post(
            f"/api/workers?job_id={job_id}",
            json={**WORKER_PAYLOAD, "email": f"c{minutes_ago}-{job_id}@example.com"},
            headers=headers or user["headers"],
        )
        assert response.status_code == 201, response.text
        worker = db_session.get(Worker, response.json()["id"])
        worker.created_at = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
        worker.application_status = application_status
        worker.analysis_status = analysis_status
        db_session.commit()
        return worker.id

    return _make


def _select(db_session, owner_id, **kwargs):
    db_session.expire_all()
    return service._get_eligible_worker_ids(db_session, owner_id, **kwargs)


class TestSelection:
    def test_newest_and_oldest_order(self, db_session, user, make_job, make_app):
        job = make_job()
        old = make_app(job, minutes_ago=30)
        mid = make_app(job, minutes_ago=20)
        new = make_app(job, minutes_ago=10)

        assert _select(db_session, user["id"], order="newest") == [new, mid, old]
        assert _select(db_session, user["id"], order="oldest") == [old, mid, new]

    def test_limit_is_applied_in_the_query(self, db_session, user, make_job, make_app):
        job = make_job()
        ids = [make_app(job, minutes_ago=m) for m in (40, 30, 20, 10)]

        assert _select(db_session, user["id"], order="oldest", limit=2) == ids[:2]

    def test_only_new_and_unanalysed_applications(self, db_session, user, make_job, make_app):
        job = make_job()
        eligible = make_app(job, minutes_ago=50)
        legacy_pending = make_app(job, minutes_ago=40, analysis_status=AnalysisStatus.PENDING)
        make_app(job, minutes_ago=30, analysis_status=AnalysisStatus.COMPLETED)
        make_app(job, minutes_ago=25, analysis_status=AnalysisStatus.FAILED)
        make_app(job, minutes_ago=20, analysis_status=AnalysisStatus.ANALYZING)
        make_app(job, minutes_ago=10, application_status=ApplicationStatus.REVIEWING)

        assert _select(db_session, user["id"]) == [eligible, legacy_pending]

    def test_company_and_position_filters(self, db_session, user, make_job, make_app):
        acme_backend = make_app(make_job("Acme", "Backend Developer"), minutes_ago=30)
        acme_frontend = make_app(make_job("Acme", "Frontend Developer"), minutes_ago=20)
        globex_backend = make_app(make_job("Globex", "Backend Developer"), minutes_ago=10)
        owner = user["id"]

        assert _select(db_session, owner, company="Acme") == [acme_backend, acme_frontend]
        assert _select(db_session, owner, position="Backend Developer") == [
            acme_backend,
            globex_backend,
        ]
        assert _select(
            db_session, owner, company="Acme", position="Backend Developer"
        ) == [acme_backend]
        # "All" = no filter.
        assert len(_select(db_session, owner, company=None, position=None)) == 3
        assert _select(db_session, owner, company="Unknown Company") == []

    def test_other_users_applications_are_never_selected(
        self, db_session, user, other_user, make_job, make_app
    ):
        mine = make_app(make_job(), minutes_ago=10)
        other_job = make_job(headers=other_user["headers"])
        make_app(other_job, minutes_ago=5, headers=other_user["headers"])

        assert _select(db_session, user["id"]) == [mine]


class TestAvailableEndpoint:
    def test_count_and_filter_options(self, client, user, make_job, make_app):
        acme = make_job("Acme", "Backend Developer")
        make_app(acme, minutes_ago=2)
        make_app(acme, minutes_ago=1)
        make_app(make_job("Globex", "QA Engineer"), minutes_ago=3)
        make_app(acme, minutes_ago=4, analysis_status=AnalysisStatus.COMPLETED)

        body = client.get(
            "/api/workers/auto-analyze/available", headers=user["headers"]
        ).json()

        assert body["count"] == 3
        assert body["options"] == [
            {"company_name": "Acme", "position": "Backend Developer", "count": 2},
            {"company_name": "Globex", "position": "QA Engineer", "count": 1},
        ]

        filtered = client.get(
            "/api/workers/auto-analyze/available",
            params={"company": "Globex", "position": ""},
            headers=user["headers"],
        ).json()
        assert filtered["count"] == 1


class TestStartEndpoint:
    @pytest.fixture(autouse=True)
    def _no_background_run(self):
        # Selection only: the background batch is exercised separately.
        with patch("app.routers.workers.asyncio.create_task") as create_task:
            create_task.side_effect = lambda coro: coro.close()
            yield

    def test_filtered_start_reports_requested_selected_and_remaining(
        self, client, user, db_session, make_job, make_app
    ):
        acme = make_job("Acme", "Backend Developer")
        ids = [make_app(acme, minutes_ago=m) for m in (30, 20, 10)]
        make_app(make_job("Globex", "Backend Developer"), minutes_ago=5)

        response = client.post(
            "/api/workers/auto-analyze",
            json={"count": 2, "order": "oldest", "company": "Acme", "position": "Backend Developer"},
            headers=user["headers"],
        )

        assert response.status_code == 201, response.text
        body = response.json()
        assert body["requested_count"] == 2
        assert body["selected_count"] == 2
        assert body["available_count"] == 3
        assert body["remaining_count"] == 1
        batch = db_session.get(AnalysisBatch, body["batch_id"])
        assert batch.worker_ids == ids[:2]

    def test_fewer_eligible_than_requested_is_not_an_error(
        self, client, user, make_job, make_app
    ):
        job = make_job()
        for minutes in (3, 2, 1):
            make_app(job, minutes_ago=minutes)

        body = client.post(
            "/api/workers/auto-analyze",
            json={"count": 100, "order": "newest"},
            headers=user["headers"],
        ).json()

        assert (body["requested_count"], body["selected_count"], body["remaining_count"]) == (
            100,
            3,
            0,
        )

    def test_no_match_creates_no_batch(self, client, user, db_session, make_job, make_app):
        make_app(make_job("Acme"), minutes_ago=1)

        response = client.post(
            "/api/workers/auto-analyze",
            json={"count": 10, "order": "oldest", "company": "Unknown Company"},
            headers=user["headers"],
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "No new, unanalyzed applications match these filters."
        assert db_session.query(AnalysisBatch).count() == 0

    @pytest.mark.parametrize("count", [0, 1001, 2.5, "ten"])
    def test_count_must_be_an_integer_from_1_to_1000(self, client, user, count):
        response = client.post(
            "/api/workers/auto-analyze",
            json={"count": count, "order": "oldest"},
            headers=user["headers"],
        )
        assert response.status_code == 422

    @pytest.mark.parametrize("count", [1, 1000])
    def test_count_bounds_are_inclusive(self, client, user, make_job, make_app, count):
        make_app(make_job(), minutes_ago=1)
        response = client.post(
            "/api/workers/auto-analyze",
            json={"count": count, "order": "oldest"},
            headers=user["headers"],
        )
        assert response.status_code == 201


class TestBatchProcessing:
    def _run(self, db_session, user_id, **kwargs):
        from app.models.user import User

        batch = service.create_auto_analyze_batch(
            db_session, db_session.get(User, user_id), count=kwargs.pop("count", 10), **kwargs
        )
        asyncio.run(service.run_batch_analysis(batch.id))
        db_session.expire_all()
        return db_session.get(AnalysisBatch, batch.id)

    def test_uses_each_applications_own_job(self, db_session, user, make_job, make_app):
        make_app(make_job("Acme", "Backend Developer"), minutes_ago=20)
        make_app(make_job("Globex", "Data Analyst"), minutes_ago=10)

        with patch(
            "app.services.application_analysis.analyze_application", new_callable=AsyncMock
        ) as analyze:
            analyze.return_value = _analysis()
            batch = self._run(db_session, user["id"], order="oldest")

        requirements = [call.kwargs["job_requirements"] for call in analyze.await_args_list]
        assert "Position: Backend Developer" in requirements[0]
        assert "Company: Acme" in requirements[0]
        assert "Position: Data Analyst" in requirements[1]
        assert "Company: Globex" in requirements[1]
        assert (batch.successful_count, batch.failed_count, batch.skipped_count) == (2, 0, 0)

    def test_one_failure_does_not_stop_the_batch(self, db_session, user, make_job, make_app):
        job = make_job()
        first, second, third = (make_app(job, minutes_ago=m) for m in (30, 20, 10))

        with patch(
            "app.services.application_analysis.analyze_application", new_callable=AsyncMock
        ) as analyze:
            analyze.side_effect = [_analysis(), AIProviderUnavailableError(), _analysis()]
            batch = self._run(db_session, user["id"], order="oldest")

        assert analyze.await_count == 3
        assert batch.status.value == "completed"
        assert (batch.successful_count, batch.failed_count, batch.skipped_count) == (2, 1, 0)
        assert batch.processed == 3 and batch.remaining == 0
        statuses = {
            worker_id: db_session.get(Worker, worker_id).analysis_status
            for worker_id in (first, second, third)
        }
        assert statuses == {
            first: AnalysisStatus.COMPLETED,
            second: AnalysisStatus.FAILED,
            third: AnalysisStatus.COMPLETED,
        }
        # The AI never touches HR's pipeline status.
        assert db_session.get(Worker, second).application_status == ApplicationStatus.NEW

    def test_items_analysed_or_deleted_meanwhile_are_skipped(
        self, client, db_session, user, make_job, make_app
    ):
        from app.models.user import User

        job = make_job()
        analysed_meanwhile, deleted_meanwhile, pending = (
            make_app(job, minutes_ago=m) for m in (30, 20, 10)
        )
        batch = service.create_auto_analyze_batch(
            db_session, db_session.get(User, user["id"]), count=10, order="oldest"
        )
        db_session.get(Worker, analysed_meanwhile).analysis_status = AnalysisStatus.COMPLETED
        db_session.commit()
        client.delete(f"/api/workers/{deleted_meanwhile}", headers=user["headers"])

        with patch(
            "app.services.application_analysis.analyze_application", new_callable=AsyncMock
        ) as analyze:
            analyze.return_value = _analysis()
            asyncio.run(service.run_batch_analysis(batch.id))

        db_session.expire_all()
        batch = db_session.get(AnalysisBatch, batch.id)
        assert analyze.await_count == 1
        assert (batch.successful_count, batch.failed_count, batch.skipped_count) == (1, 0, 2)
        assert db_session.get(Worker, pending).analysis_status == AnalysisStatus.COMPLETED

    def test_progress_endpoint_reports_skipped(self, client, db_session, user, make_job, make_app):
        make_app(make_job(), minutes_ago=1)
        with patch(
            "app.services.application_analysis.analyze_application", new_callable=AsyncMock
        ) as analyze:
            analyze.return_value = _analysis()
            batch = self._run(db_session, user["id"])

        body = client.get(
            f"/api/workers/auto-analyze/{batch.id}", headers=user["headers"]
        ).json()
        assert body["successful"] == 1
        assert body["skipped"] == 0
        assert body["processed"] == 1
        assert body["status"] == "completed"
