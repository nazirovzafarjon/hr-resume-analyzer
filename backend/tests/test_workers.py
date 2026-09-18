"""Tests for worker/candidate endpoints and worker CRUD functions.

Workers belong to a job owned by the authenticated HR user. Other users'
workers behave like "not found" (no existence/ownership details leak).
"""

import pytest

from tests.payloads import WORKER_PAYLOAD

from app.crud import worker as worker_crud
from app.models.worker import HiringStatus, InterviewStatus
from app.schemas.worker import WorkerCreate, WorkerUpdate


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


class TestCreateWorker:
    def test_create_worker_success(self, client, worker_factory, sample_job):
        response = worker_factory(sample_job["id"])
        assert response.status_code == 201
        body = response.json()
        assert body["name"] == "Jane Doe"
        assert body["job_id"] == sample_job["id"]
        assert body["hiring_status"] == "hire"
        assert body["interview_status"] == "not_completed"

    def test_create_worker_increments_leads_count(self, client, worker_factory, sample_job):
        worker_factory(sample_job["id"])
        worker_factory(sample_job["id"])
        job = client.get(f"/api/jobs/{sample_job['id']}", headers=sample_job["headers"]).json()
        assert job["leads_count"] == 2

    def test_create_worker_for_unowned_job_returns_404(self, client, sample_job, other_user):
        response = client.post(
            f"/api/workers?job_id={sample_job['id']}",
            json=WORKER_PAYLOAD,
            headers=other_user["headers"],
        )
        assert response.status_code == 404

    def test_create_worker_requires_job_id_param(self, client, user):
        response = client.post("/api/workers", json=WORKER_PAYLOAD, headers=user["headers"])
        assert response.status_code == 422

    def test_create_worker_requires_auth(self, client, sample_job):
        response = client.post(f"/api/workers?job_id={sample_job['id']}", json=WORKER_PAYLOAD)
        assert response.status_code == 401

    def test_create_worker_with_empty_name(self, client, worker_factory, sample_job):
        payload = dict(WORKER_PAYLOAD, name="")
        assert worker_factory(sample_job["id"], payload=payload).status_code == 422


# ---------------------------------------------------------------------------
# Read / list
# ---------------------------------------------------------------------------


class TestListWorkers:
    def test_list_workers_for_job(self, client, worker_factory, sample_job):
        worker_factory(sample_job["id"])
        worker_factory(sample_job["id"], payload=dict(WORKER_PAYLOAD, name="Bob Smith"))
        response = client.get(f"/api/workers?job_id={sample_job['id']}", headers=sample_job["headers"])
        assert response.status_code == 200
        assert {worker["name"] for worker in response.json()} == {"Jane Doe", "Bob Smith"}

    def test_list_workers_for_unowned_job_returns_404(self, client, sample_job, other_user):
        response = client.get(f"/api/workers?job_id={sample_job['id']}", headers=other_user["headers"])
        assert response.status_code == 404

    def test_list_workers_without_job_id_param_returns_all_owned(self, client, worker_factory, sample_job):
        worker_factory(sample_job["id"])
        worker_factory(sample_job["id"], payload=dict(WORKER_PAYLOAD, name="Bob Smith"))
        response = client.get("/api/workers", headers=sample_job["headers"])
        assert response.status_code == 200
        assert {worker["name"] for worker in response.json()} == {"Jane Doe", "Bob Smith"}

    def test_list_workers_all_view_scoped_to_owner(self, client, worker_factory, sample_job, other_user):
        worker_factory(sample_job["id"])
        response = client.get("/api/workers", headers=other_user["headers"])
        assert response.status_code == 200
        assert response.json() == []

    def test_list_workers_filter_by_hiring_status(self, client, worker_factory, sample_job):
        worker_factory(sample_job["id"])
        weak = worker_factory(sample_job["id"], payload=dict(WORKER_PAYLOAD, name="Weak Match"))
        assert client.patch(
            f"/api/workers/{weak.json()['id']}",
            json={"hiring_status": "weak_hire"},
            headers=sample_job["headers"],
        ).status_code == 200
        response = client.get(
            "/api/workers?hiring_status=weak_hire", headers=sample_job["headers"]
        )
        assert response.status_code == 200
        assert [worker["name"] for worker in response.json()] == ["Weak Match"]

    def test_list_workers_filter_by_interview_status(self, client, worker_factory, sample_job):
        worker_factory(sample_job["id"])
        done = worker_factory(sample_job["id"], payload=dict(WORKER_PAYLOAD, name="Interviewed"))
        assert client.patch(
            f"/api/workers/{done.json()['id']}",
            json={"interview_status": "completed"},
            headers=sample_job["headers"],
        ).status_code == 200
        response = client.get(
            "/api/workers?interview_status=completed", headers=sample_job["headers"]
        )
        assert response.status_code == 200
        assert [worker["name"] for worker in response.json()] == ["Interviewed"]

    def test_list_workers_with_pagination(self, client, worker_factory, sample_job):
        worker_factory(sample_job["id"])
        worker_factory(sample_job["id"], payload=dict(WORKER_PAYLOAD, name="Bob Smith"))
        response = client.get("/api/workers?skip=1&limit=1", headers=sample_job["headers"])
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_list_workers_invalid_hiring_status_returns_422(self, client, user):
        response = client.get("/api/workers?hiring_status=maybe", headers=user["headers"])
        assert response.status_code == 422
class TestGetWorker:
    def test_get_own_worker(self, client, sample_worker):
        response = client.get(f"/api/workers/{sample_worker['id']}", headers=sample_worker["headers"])
        assert response.status_code == 200
        assert response.json()["name"] == "Jane Doe"

    def test_get_worker_from_other_users_job_returns_404(self, client, sample_worker, other_user):
        response = client.get(f"/api/workers/{sample_worker['id']}", headers=other_user["headers"])
        assert response.status_code == 404

    def test_get_missing_worker_returns_404(self, client, user):
        assert client.get("/api/workers/999999", headers=user["headers"]).status_code == 404


# ---------------------------------------------------------------------------
# Update (PATCH): hiring / interview status
# ---------------------------------------------------------------------------


class TestUpdateWorker:
    def test_update_hiring_status(self, client, sample_worker):
        response = client.patch(
            f"/api/workers/{sample_worker['id']}",
            json={"hiring_status": "strong_hire"},
            headers=sample_worker["headers"],
        )
        assert response.status_code == 200
        assert response.json()["hiring_status"] == "strong_hire"
        assert response.json()["interview_status"] == "not_completed"  # untouched

    def test_update_interview_status(self, client, sample_worker):
        response = client.patch(
            f"/api/workers/{sample_worker['id']}",
            json={"interview_status": "completed"},
            headers=sample_worker["headers"],
        )
        assert response.status_code == 200
        assert response.json()["interview_status"] == "completed"

    def test_update_with_invalid_hiring_status(self, client, sample_worker):
        response = client.patch(
            f"/api/workers/{sample_worker['id']}",
            json={"hiring_status": "maybe"},
            headers=sample_worker["headers"],
        )
        assert response.status_code == 422

    def test_update_with_invalid_interview_status(self, client, sample_worker):
        response = client.patch(
            f"/api/workers/{sample_worker['id']}",
            json={"interview_status": "almost_done"},
            headers=sample_worker["headers"],
        )
        assert response.status_code == 422

    def test_update_other_users_worker_returns_404(self, client, sample_worker, other_user):
        response = client.patch(
            f"/api/workers/{sample_worker['id']}",
            json={"hiring_status": "hire"},
            headers=other_user["headers"],
        )
        assert response.status_code == 404

    def test_update_missing_worker_returns_404(self, client, user):
        response = client.patch("/api/workers/999999", json={"hiring_status": "hire"}, headers=user["headers"])
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Analyze: AI screening result persisted onto the worker
# ---------------------------------------------------------------------------


SAMPLE_ANALYSIS_DATA = {
    "match_percentage": 92.5,
    "summary": "Strong candidate with relevant experience in Python and FastAPI.",
    "matched_requirements": ["Python", "FastAPI"],
    "missing_requirements": ["PostgreSQL"],
    "matched_skills": ["Python", "FastAPI"],
    "missing_skills": ["PostgreSQL"],
    "strengths": ["Solid experience in REST APIs"],
    "weaknesses": ["No database optimization shown"],
    "risks": [],
    "experience_analysis": "3 years backend experience.",
    "education_analysis": "B.S. in Computer Science.",
    "relevant_experience": ["Software Engineer at TechCo"],
    "relevant_projects": ["Resume Analyzer API"],
    "ai_recommendation": "strong_hire",
}


class TestAnalyzeWorker:
    def test_analyze_saves_score_details_and_recommendation(self, client, sample_worker):
        from unittest.mock import AsyncMock, patch
        from app.schemas.application_analysis import ApplicationAnalysis

        mock_result = ApplicationAnalysis(**SAMPLE_ANALYSIS_DATA)
        with patch(
            "app.services.application_analysis.analyze_application",
            new_callable=AsyncMock,
        ) as mock_analyze:
            mock_analyze.return_value = mock_result
            response = client.post(
                f"/api/workers/{sample_worker['id']}/analyze",
                headers=sample_worker["headers"],
            )
        assert response.status_code == 200
        body = response.json()
        assert body["ai_score"] == 92.5
        assert body["analysis_status"] == "completed"
        # HR fields remain untouched by the AI:
        assert body["application_status"] == "new"
        assert body["hiring_status"] == "hire"
        assert body["interview_status"] == "not_completed"
        # Analysis payload is present:
        assert body["analysis"] is not None
        assert body["analysis"]["match_percentage"] == 92.5
        assert body["analysis"]["ai_recommendation"] == "strong_hire"
        assert body["analysis"]["matched_skills"] == ["Python", "FastAPI"]

    def test_analyze_without_force_skips_if_completed(self, client, sample_worker):
        from unittest.mock import AsyncMock, patch
        from app.schemas.application_analysis import ApplicationAnalysis

        mock_result = ApplicationAnalysis(**SAMPLE_ANALYSIS_DATA)
        with patch(
            "app.services.application_analysis.analyze_application",
            new_callable=AsyncMock,
        ) as mock_analyze:
            mock_analyze.return_value = mock_result
            # First run:
            client.post(
                f"/api/workers/{sample_worker['id']}/analyze",
                headers=sample_worker["headers"],
            )
            assert mock_analyze.call_count == 1

            # Second run without force=True should not re-trigger AI:
            client.post(
                f"/api/workers/{sample_worker['id']}/analyze",
                headers=sample_worker["headers"],
            )
            assert mock_analyze.call_count == 1

    def test_analyze_failure_persists_error_and_keeps_worker(self, client, sample_worker):
        from unittest.mock import AsyncMock, patch
        from app.services.ai.job_analyzer import AIServiceError

        with patch(
            "app.services.application_analysis.analyze_application",
            new_callable=AsyncMock,
        ) as mock_analyze:
            mock_analyze.side_effect = AIServiceError("OpenRouter rate limit exceeded", status_code=429)
            response = client.post(
                f"/api/workers/{sample_worker['id']}/analyze?force=true",
                headers=sample_worker["headers"],
            )
        # Endpoint returns the worker with failed analysis status so UI can show retry:
        assert response.status_code == 200
        body = response.json()
        assert body["analysis_status"] == "failed"
        assert "OpenRouter rate limit" in body["analysis_error"]
        # Worker itself was not deleted:
        get_res = client.get(f"/api/workers/{sample_worker['id']}", headers=sample_worker["headers"])
        assert get_res.status_code == 200
        assert get_res.json()["name"] == "Jane Doe"

    def test_analyze_other_users_worker_returns_404(self, client, sample_worker, other_user):
        response = client.post(
            f"/api/workers/{sample_worker['id']}/analyze",
            headers=other_user["headers"],
        )
        assert response.status_code == 404

    def test_analyze_missing_worker_returns_404(self, client, user):
        response = client.post(
            "/api/workers/999999/analyze",
            headers=user["headers"],
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Convert to candidate & Candidate pipeline
# ---------------------------------------------------------------------------


class TestConvertToCandidate:
    def test_convert_to_candidate_success(self, client, sample_worker):
        response = client.post(
            f"/api/workers/{sample_worker['id']}/convert-to-candidate",
            headers=sample_worker["headers"],
        )
        assert response.status_code == 200
        body = response.json()
        assert body["is_candidate"] is True
        assert body["candidate_at"] is not None

    def test_convert_to_candidate_idempotent(self, client, sample_worker):
        res1 = client.post(
            f"/api/workers/{sample_worker['id']}/convert-to-candidate",
            headers=sample_worker["headers"],
        )
        res2 = client.post(
            f"/api/workers/{sample_worker['id']}/convert-to-candidate",
            headers=sample_worker["headers"],
        )
        assert res1.status_code == 200
        assert res2.status_code == 200
        assert res1.json()["candidate_at"] == res2.json()["candidate_at"]

    def test_convert_to_candidate_unowned_returns_404(self, client, sample_worker, other_user):
        response = client.post(
            f"/api/workers/{sample_worker['id']}/convert-to-candidate",
            headers=other_user["headers"],
        )
        assert response.status_code == 404

    def test_candidate_only_filter(self, client, worker_factory, sample_job):
        w1 = worker_factory(sample_job["id"]).json()
        w2 = worker_factory(sample_job["id"], payload=dict(WORKER_PAYLOAD, name="Candidate Two")).json()

        # Convert w2 to candidate:
        client.post(
            f"/api/workers/{w2['id']}/convert-to-candidate",
            headers=sample_job["headers"],
        )

        # Listing with candidate_only=true returns only w2:
        res = client.get("/api/workers?candidate_only=true", headers=sample_job["headers"])
        assert res.status_code == 200
        items = res.json()
        assert len(items) == 1
        assert items[0]["id"] == w2["id"]


# ---------------------------------------------------------------------------
# Stored Analysis GET endpoint
# ---------------------------------------------------------------------------


class TestWorkerAnalysisEndpoint:
    def test_get_worker_analysis_returns_stored_data(self, client, sample_worker):
        from unittest.mock import AsyncMock, patch
        from app.schemas.application_analysis import ApplicationAnalysis

        mock_result = ApplicationAnalysis(**SAMPLE_ANALYSIS_DATA)
        with patch(
            "app.services.application_analysis.analyze_application",
            new_callable=AsyncMock,
        ) as mock_analyze:
            mock_analyze.return_value = mock_result
            client.post(
                f"/api/workers/{sample_worker['id']}/analyze",
                headers=sample_worker["headers"],
            )

        # GET /api/workers/{id}/analysis should read stored data:
        response = client.get(
            f"/api/workers/{sample_worker['id']}/analysis",
            headers=sample_worker["headers"],
        )
        assert response.status_code == 200
        body = response.json()
        assert body["worker_id"] == sample_worker["id"]
        assert body["analysis_status"] == "completed"
        assert body["ai_score"] == 92.5
        assert body["analysis"]["match_percentage"] == 92.5
        assert body["analysis"]["ai_recommendation"] == "strong_hire"

    def test_get_worker_analysis_unowned_returns_404(self, client, sample_worker, other_user):
        response = client.get(
            f"/api/workers/{sample_worker['id']}/analysis",
            headers=other_user["headers"],
        )
        assert response.status_code == 404



# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


class TestDeleteWorker:
    def test_delete_worker_success(self, client, sample_worker):
        response = client.delete(f"/api/workers/{sample_worker['id']}", headers=sample_worker["headers"])
        assert response.status_code == 204
        missing = client.get(f"/api/workers/{sample_worker['id']}", headers=sample_worker["headers"])
        assert missing.status_code == 404

    def test_delete_other_users_worker_returns_404(self, client, sample_worker, other_user):
        response = client.delete(f"/api/workers/{sample_worker['id']}", headers=other_user["headers"])
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Worker CRUD functions
# ---------------------------------------------------------------------------


class TestWorkerCrud:
    def _create_job_with_owner(self, db_session, owner_id, **overrides):
        from app.crud.job import create_job as job_crud_create
        from app.schemas.job import JobCreate
        from tests.payloads import JOB_PAYLOAD

        return job_crud_create(
            db_session, owner_id=owner_id, payload=JobCreate(**{**JOB_PAYLOAD, **overrides})
        )

    def _create_owner(self, db_session, email="owner@example.com"):
        from app.crud import user as user_crud
        from app.schemas.user import UserCreate

        return user_crud.create_user(
            db_session, UserCreate(email=email, full_name="Owner", password="PassPass123")
        )

    def test_create_worker(self, db_session):
        owner = self._create_owner(db_session)
        job = self._create_job_with_owner(db_session, owner.id)
        worker = worker_crud.create_worker(db_session, job_id=job.id, payload=WorkerCreate(**WORKER_PAYLOAD))
        assert worker.id is not None
        assert worker.job_id == job.id
        assert worker.hiring_status == HiringStatus.HIRE
        assert worker.interview_status == InterviewStatus.NOT_COMPLETED

    def test_get_worker(self, db_session):
        owner = self._create_owner(db_session)
        job = self._create_job_with_owner(db_session, owner.id)
        worker = worker_crud.create_worker(db_session, job_id=job.id, payload=WorkerCreate(**WORKER_PAYLOAD))
        assert worker_crud.get_worker(db_session, worker.id) is worker
        assert worker_crud.get_worker(db_session, 999999) is None

    def test_get_workers_for_job_filters_by_job(self, db_session):
        owner = self._create_owner(db_session)
        job_a = self._create_job_with_owner(db_session, owner.id, position="Dev")
        job_b = self._create_job_with_owner(db_session, owner.id, position="QA")
        worker_crud.create_worker(db_session, job_id=job_a.id, payload=WorkerCreate(**WORKER_PAYLOAD))
        worker_crud.create_worker(db_session, job_id=job_b.id, payload=WorkerCreate(**WORKER_PAYLOAD))
        workers = worker_crud.get_workers_for_job(db_session, job_id=job_a.id)
        assert len(workers) == 1
        assert workers[0].job_id == job_a.id

    def test_list_workers_scopes_to_owner_and_filters(self, db_session):
        owner = self._create_owner(db_session)
        other = self._create_owner(db_session, email="other@example.com")
        job = self._create_job_with_owner(db_session, owner.id, position="Dev")
        other_job = self._create_job_with_owner(db_session, other.id, position="QA")
        strong = worker_crud.create_worker(db_session, job_id=job.id, payload=WorkerCreate(**WORKER_PAYLOAD))
        worker_crud.create_worker(db_session, job_id=job.id, payload=WorkerCreate(**{**WORKER_PAYLOAD, "name": "Second"}))
        worker_crud.create_worker(db_session, job_id=other_job.id, payload=WorkerCreate(**{**WORKER_PAYLOAD, "name": "Foreign"}))

        all_owned = worker_crud.list_workers(db_session, owner.id)
        assert {w.name for w in all_owned} == {"Jane Doe", "Second"}

        filtered = worker_crud.list_workers(db_session, owner.id, hiring_status=HiringStatus.HIRE)
        assert len(filtered) == 2

        worker_crud.update_worker(db_session, strong, WorkerUpdate(hiring_status=HiringStatus.STRONG_HIRE))
        filtered = worker_crud.list_workers(db_session, owner.id, hiring_status=HiringStatus.STRONG_HIRE)
        assert [w.id for w in filtered] == [strong.id]

        by_job = worker_crud.list_workers(db_session, owner.id, job_id=job.id)
        assert all(w.job_id == job.id for w in by_job)

    def test_list_workers_paginates(self, db_session):
        owner = self._create_owner(db_session)
        job = self._create_job_with_owner(db_session, owner.id, position="Dev")
        for name in ("One", "Two", "Three"):
            worker_crud.create_worker(
                db_session, job_id=job.id, payload=WorkerCreate(**{**WORKER_PAYLOAD, "name": name})
            )
        page = worker_crud.list_workers(db_session, owner.id, skip=1, limit=2)
        assert len(page) == 2
        # Ordered by created_at desc: newest first.
        assert [w.name for w in page] == ["Two", "One"]

    def test_get_recent_workers_across_owners_jobs(self, db_session):
        owner_a = self._create_owner(db_session, email="owner-a@example.com")
        owner_b = self._create_owner(db_session, email="owner-b@example.com")
        job_a = self._create_job_with_owner(db_session, owner_a.id, position="Dev")
        job_b = self._create_job_with_owner(db_session, owner_b.id, position="QA")

        worker_crud.create_worker(db_session, job_id=job_a.id, payload=WorkerCreate(**WORKER_PAYLOAD))
        worker_crud.create_worker(db_session, job_id=job_b.id, payload=WorkerCreate(**WORKER_PAYLOAD))

        recent = worker_crud.get_recent_workers(db_session, owner_id=owner_a.id, limit=5)
        assert [w.job_id for w in recent] == [job_a.id]
        # The job is eagerly loaded with the worker (no lazy-load crash).
        assert recent[0].job.company_name == "Acme Corp"

    def test_update_worker_applies_only_submitted_fields(self, db_session):
        owner = self._create_owner(db_session)
        job = self._create_job_with_owner(db_session, owner.id)
        worker = worker_crud.create_worker(db_session, job_id=job.id, payload=WorkerCreate(**WORKER_PAYLOAD))
        updated = worker_crud.update_worker(db_session, worker, WorkerUpdate(hiring_status=HiringStatus.STRONG_HIRE))
        assert updated.hiring_status == HiringStatus.STRONG_HIRE
        assert updated.interview_status == InterviewStatus.NOT_COMPLETED  # untouched

    def test_delete_worker(self, db_session):
        owner = self._create_owner(db_session)
        job = self._create_job_with_owner(db_session, owner.id)
        worker = worker_crud.create_worker(db_session, job_id=job.id, payload=WorkerCreate(**WORKER_PAYLOAD))
        worker_crud.delete_worker(db_session, worker.id)
        assert worker_crud.get_worker(db_session, worker.id) is None