"""Tests for job endpoints and job CRUD functions.

Jobs are scoped to the authenticated HR user: endpoints only ever see the
current user's own jobs (other users' jobs behave like "not found").
"""

import json
from unittest.mock import AsyncMock, patch

import pytest

from tests.payloads import JOB_PAYLOAD  # noqa: F401  (shared test data)

from app.crud import job as job_crud
from app.schemas.job import JobAIAnalysisResult, JobCreate, JobUpdate


VACANCY_CONTENT = """
We are looking for a Senior Python Developer to join our team at Acme Corp.

Responsibilities:
- Build and maintain backend services using Python and FastAPI
- Design and implement REST APIs
- Work with PostgreSQL databases
- Collaborate with frontend team

Requirements:
- 3+ years of Python experience
- Strong knowledge of FastAPI, PostgreSQL
- Experience with Docker and CI/CD
- Good communication skills
"""

AI_ANALYSIS_RESPONSE = {
    "company_name": "Acme Corp",
    "position": "Senior Python Developer",
    "description": "Build and maintain backend services using Python and FastAPI. Design and implement REST APIs. Work with PostgreSQL databases. Collaborate with frontend team.",
    "required_skills": "Python, FastAPI, PostgreSQL, Docker, CI/CD",
    "required_experience": "3+ years",
}


def _create_owner(db_session, email="owner@example.com"):
    """Create a user row so jobs have a valid owner_id (FK requirement)."""
    from app.crud import user as user_crud
    from app.schemas.user import UserCreate

    return user_crud.create_user(
        db_session, UserCreate(email=email, full_name="Owner", password="PassPass123")
    )


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


class TestCreateJob:
    def test_create_job_success(self, client, user):
        response = client.post("/api/jobs", json=JOB_PAYLOAD, headers=user["headers"])
        assert response.status_code == 201
        body = response.json()
        assert body["company_name"] == "Acme Corp"
        assert body["position"] == "Backend Developer"
        assert body["required_skills"] == "Python, FastAPI, PostgreSQL"
        assert body["leads_count"] == 0
        assert body["id"] > 0

    def test_create_job_persists_owner(self, client, user, db_session):
        response = client.post("/api/jobs", json=JOB_PAYLOAD, headers=user["headers"])
        job = job_crud.get_job(db_session, response.json()["id"])
        assert job is not None
        assert job.owner_id == user["id"]

    def test_create_job_requires_auth(self, client):
        assert client.post("/api/jobs", json=JOB_PAYLOAD).status_code == 401

    def test_create_job_missing_required_fields(self, client, user):
        response = client.post("/api/jobs", json={"company_name": "Acme"}, headers=user["headers"])
        assert response.status_code == 422  # position is required

    def test_create_job_empty_company_name(self, client, user):
        payload = dict(JOB_PAYLOAD, company_name="")
        assert client.post("/api/jobs", json=payload, headers=user["headers"]).status_code == 422


# ---------------------------------------------------------------------------
# Read / list
# ---------------------------------------------------------------------------


class TestListJobs:
    def test_list_jobs_returns_own_jobs(self, client, user, sample_job):
        response = client.get("/api/jobs", headers=user["headers"])
        assert response.status_code == 200
        jobs = response.json()
        assert len(jobs) == 1
        assert jobs[0]["id"] == sample_job["id"]

    def test_list_jobs_excludes_other_users_jobs(self, client, sample_job, other_user):
        response = client.get("/api/jobs", headers=other_user["headers"])
        assert response.status_code == 200
        assert response.json() == []

    def test_list_jobs_requires_auth(self, client):
        assert client.get("/api/jobs").status_code == 401


class TestGetJob:
    def test_get_own_job(self, client, sample_job):
        response = client.get(f"/api/jobs/{sample_job['id']}", headers=sample_job["headers"])
        assert response.status_code == 200
        assert response.json()["position"] == "Backend Developer"

    def test_get_other_users_job_is_not_found(self, client, sample_job, other_user):
        response = client.get(f"/api/jobs/{sample_job['id']}", headers=other_user["headers"])
        assert response.status_code == 404

    def test_get_missing_job_returns_404(self, client, user):
        assert client.get("/api/jobs/999999", headers=user["headers"]).status_code == 404
# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


class TestUpdateJob:
    def test_update_job_success(self, client, sample_job):
        response = client.put(
            f"/api/jobs/{sample_job['id']}",
            json={"position": "Senior Backend Developer"},
            headers=sample_job["headers"],
        )
        assert response.status_code == 200
        body = response.json()
        assert body["position"] == "Senior Backend Developer"
        # Untouched fields keep their values.
        assert body["company_name"] == "Acme Corp"
        assert body["required_skills"] == "Python, FastAPI, PostgreSQL"

    def test_update_other_users_job_is_not_found(self, client, sample_job, other_user):
        response = client.put(
            f"/api/jobs/{sample_job['id']}",
            json={"position": "Hacked"},
            headers=other_user["headers"],
        )
        assert response.status_code == 404

    def test_update_missing_job_returns_404(self, client, user):
        response = client.put("/api/jobs/999999", json={"position": "X"}, headers=user["headers"])
        assert response.status_code == 404

    def test_update_with_empty_company_name(self, client, sample_job):
        response = client.put(
            f"/api/jobs/{sample_job['id']}",
            json={"company_name": ""},
            headers=sample_job["headers"],
        )
        assert response.status_code == 422

    def test_update_requires_auth(self, client, sample_job):
        assert client.put(f"/api/jobs/{sample_job['id']}", json={"position": "X"}).status_code == 401


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


class TestDeleteJob:
    def test_delete_job_success(self, client, sample_job):
        response = client.delete(f"/api/jobs/{sample_job['id']}", headers=sample_job["headers"])
        assert response.status_code == 204
        assert client.get("/api/jobs", headers=sample_job["headers"]).json() == []

    def test_delete_job_with_workers_cascades(self, client, sample_job, worker_factory, db_session):
        worker_factory(sample_job["id"])
        response = client.delete(f"/api/jobs/{sample_job['id']}", headers=sample_job["headers"])
        assert response.status_code == 204
        assert job_crud.get_job(db_session, sample_job["id"]) is None
        from app.crud.worker import get_workers_for_job

        assert get_workers_for_job(db_session, sample_job["id"]) == []

    def test_delete_other_users_job_is_not_found(self, client, sample_job, other_user):
        response = client.delete(f"/api/jobs/{sample_job['id']}", headers=other_user["headers"])
        assert response.status_code == 404

    def test_delete_missing_job_returns_404(self, client, user):
        assert client.delete("/api/jobs/999999", headers=user["headers"]).status_code == 404
# ---------------------------------------------------------------------------
# Job CRUD functions
# ---------------------------------------------------------------------------


class TestJobCrud:
    def test_create_job(self, db_session):
        owner = _create_owner(db_session)
        job = job_crud.create_job(db_session, owner_id=owner.id, payload=JobCreate(**JOB_PAYLOAD))
        assert job.id is not None
        assert job.company_name == "Acme Corp"
        assert job.leads_count == 0

    def test_get_job(self, db_session):
        owner = _create_owner(db_session)
        job = job_crud.create_job(db_session, owner_id=owner.id, payload=JobCreate(**JOB_PAYLOAD))
        assert job_crud.get_job(db_session, job.id) is job
        assert job_crud.get_job(db_session, 999999) is None

    def test_get_jobs_for_user_filters_by_owner(self, db_session):
        owner = _create_owner(db_session)
        other = _create_owner(db_session, email="other@example.com")
        job_crud.create_job(db_session, owner_id=owner.id, payload=JobCreate(**JOB_PAYLOAD))
        job_crud.create_job(
            db_session, owner_id=other.id, payload=JobCreate(**{**JOB_PAYLOAD, "company_name": "Other"})
        )
        assert len(job_crud.get_jobs_for_user(db_session, owner_id=owner.id)) == 1

    def test_get_recent_jobs_limits_result(self, db_session):
        owner = _create_owner(db_session)
        for i in range(3):
            job_crud.create_job(
                db_session,
                owner_id=owner.id,
                payload=JobCreate(**{**JOB_PAYLOAD, "position": f"Position {i}"}),
            )
        recent = job_crud.get_recent_jobs(db_session, owner_id=owner.id, limit=2)
        assert len(recent) == 2

    def test_update_job_applies_only_submitted_fields(self, db_session):
        owner = _create_owner(db_session)
        job = job_crud.create_job(db_session, owner_id=owner.id, payload=JobCreate(**JOB_PAYLOAD))
        updated = job_crud.update_job(db_session, job, JobUpdate(position="Team Lead"))
        assert updated.position == "Team Lead"
        assert updated.company_name == "Acme Corp"  # untouched

    def test_delete_job(self, db_session):
        owner = _create_owner(db_session)
        job = job_crud.create_job(db_session, owner_id=owner.id, payload=JobCreate(**JOB_PAYLOAD))
        job_crud.delete_job(db_session, job.id)
        assert job_crud.get_job(db_session, job.id) is None


# ---------------------------------------------------------------------------
# AI Vacancy Analysis
# ---------------------------------------------------------------------------


class TestAnalyzeJob:
    """Tests for POST /api/jobs/analyze endpoint."""

    def test_analyze_job_success(self, client, user):
        """Test successful AI analysis of a vacancy."""
        with patch("app.routers.jobs.analyze_vacancy", new_callable=AsyncMock) as mock_analyze:
            mock_analyze.return_value = JobAIAnalysisResult(**AI_ANALYSIS_RESPONSE)
            response = client.post(
                "/api/jobs/analyze",
                json={"content": VACANCY_CONTENT},
                headers=user["headers"],
            )
        assert response.status_code == 200
        body = response.json()
        assert body["company_name"] == "Acme Corp"
        assert body["position"] == "Senior Python Developer"
        assert "Python" in body["required_skills"]
        assert "FastAPI" in body["required_skills"]
        assert body["required_experience"] == "3+ years"

    def test_analyze_job_requires_auth(self, client):
        """Test that AI analysis endpoint requires authentication."""
        response = client.post("/api/jobs/analyze", json={"content": VACANCY_CONTENT})
        assert response.status_code == 401

    def test_analyze_job_empty_content(self, client, user):
        """Test that empty content returns validation error."""
        response = client.post(
            "/api/jobs/analyze",
            json={"content": ""},
            headers=user["headers"],
        )
        assert response.status_code == 422

    def test_analyze_job_content_too_long(self, client, user):
        """Test that overly long content returns validation error."""
        long_content = "x" * 50001
        response = client.post(
            "/api/jobs/analyze",
            json={"content": long_content},
            headers=user["headers"],
        )
        assert response.status_code == 422

    def test_analyze_job_provider_unavailable(self, client, user):
        """Test handling of AI provider unavailable (503)."""
        from app.services.ai.job_analyzer import AIProviderUnavailableError

        with patch("app.routers.jobs.analyze_vacancy", new_callable=AsyncMock) as mock_analyze:
            mock_analyze.side_effect = AIProviderUnavailableError()
            response = client.post(
                "/api/jobs/analyze",
                json={"content": VACANCY_CONTENT},
                headers=user["headers"],
            )
        assert response.status_code == 503
        assert "temporarily unavailable" in response.json()["detail"].lower()

    def test_analyze_job_provider_auth_failure(self, client, user):
        """Test handling of AI provider authentication failure (502)."""
        from app.services.ai.job_analyzer import AIProviderAuthError

        with patch("app.routers.jobs.analyze_vacancy", new_callable=AsyncMock) as mock_analyze:
            mock_analyze.side_effect = AIProviderAuthError()
            response = client.post(
                "/api/jobs/analyze",
                json={"content": VACANCY_CONTENT},
                headers=user["headers"],
            )
        assert response.status_code == 502
        assert "authentication failed" in response.json()["detail"].lower()

    def test_analyze_job_invalid_response(self, client, user):
        """Test handling of invalid AI response (502)."""
        from app.services.ai.job_analyzer import AIInvalidResponseError

        with patch("app.routers.jobs.analyze_vacancy", new_callable=AsyncMock) as mock_analyze:
            mock_analyze.side_effect = AIInvalidResponseError()
            response = client.post(
                "/api/jobs/analyze",
                json={"content": VACANCY_CONTENT},
                headers=user["headers"],
            )
        assert response.status_code == 502
        assert "invalid response" in response.json()["detail"].lower()

    def test_analyze_job_rate_limit(self, client, user):
        """Test handling of AI provider rate limit (503)."""
        from app.services.ai.job_analyzer import AIProviderUnavailableError

        with patch("app.routers.jobs.analyze_vacancy", new_callable=AsyncMock) as mock_analyze:
            mock_analyze.side_effect = AIProviderUnavailableError("AI service rate limit exceeded. Please try again later.")
            response = client.post(
                "/api/jobs/analyze",
                json={"content": VACANCY_CONTENT},
                headers=user["headers"],
            )
        assert response.status_code == 503
        assert "rate limit" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Public Apply Endpoint
# ---------------------------------------------------------------------------


class TestPublicApply:
    """Tests for POST /api/public/apply/{job_id} endpoint."""

    def test_public_apply_success(self, client, sample_job):
        """Test successful public application submission."""
        # Use the job's public_id for the public endpoint
        job_data = sample_job["data"]
        # The sample_job fixture doesn't include public_id in the response yet
        # We need to fetch the job to get its public_id
        response = client.get(f"/api/jobs/{sample_job['id']}", headers=sample_job["headers"])
        assert response.status_code == 200
        job = response.json()
        public_id = job["public_id"]

        # Submit application
        files = {"resume": ("resume.pdf", b"fake pdf content", "application/pdf")}
        data = {"name": "John Doe", "email": "john@example.com"}
        response = client.post(
            f"/api/public/apply/{public_id}",
            data=data,
            files=files,
        )
        assert response.status_code == 201
        body = response.json()
        assert body["name"] == "John Doe"
        assert body["email"] == "john@example.com"
        assert body["job_id"] == sample_job["id"]

        # Verify leads_count incremented
        response = client.get(f"/api/jobs/{sample_job['id']}", headers=sample_job["headers"])
        assert response.status_code == 200
        job = response.json()
        assert job["leads_count"] == 1

    def test_public_apply_invalid_file_type(self, client, sample_job):
        """Test that invalid file type returns 400."""
        response = client.get(f"/api/jobs/{sample_job['id']}", headers=sample_job["headers"])
        job = response.json()
        public_id = job["public_id"]

        files = {"resume": ("resume.exe", b"malicious content", "application/x-msdownload")}
        data = {"name": "John Doe", "email": "john@example.com"}
        response = client.post(
            f"/api/public/apply/{public_id}",
            data=data,
            files=files,
        )
        assert response.status_code == 400
        assert "invalid file type" in response.json()["detail"].lower()

    def test_public_apply_file_too_large(self, client, sample_job):
        """Test that file exceeding size limit returns 400."""
        response = client.get(f"/api/jobs/{sample_job['id']}", headers=sample_job["headers"])
        job = response.json()
        public_id = job["public_id"]

        large_content = b"x" * (11 * 1024 * 1024)  # 11MB
        files = {"resume": ("resume.pdf", large_content, "application/pdf")}
        data = {"name": "John Doe", "email": "john@example.com"}
        response = client.post(
            f"/api/public/apply/{public_id}",
            data=data,
            files=files,
        )
        assert response.status_code == 400
        assert "file size exceeds" in response.json()["detail"].lower()

    def test_public_apply_job_not_found(self, client):
        """Test that applying to non-existent job returns 404."""
        import uuid
        fake_id = uuid.uuid4()
        files = {"resume": ("resume.pdf", b"content", "application/pdf")}
        data = {"name": "John Doe", "email": "john@example.com"}
        response = client.post(
            f"/api/public/apply/{fake_id}",
            data=data,
            files=files,
        )
        assert response.status_code == 404

    def test_public_apply_missing_fields(self, client, sample_job):
        """Test that missing required fields returns 422."""
        response = client.get(f"/api/jobs/{sample_job['id']}", headers=sample_job["headers"])
        job = response.json()
        public_id = job["public_id"]

        # Missing name
        files = {"resume": ("resume.pdf", b"content", "application/pdf")}
        data = {"email": "john@example.com"}
        response = client.post(
            f"/api/public/apply/{public_id}",
            data=data,
            files=files,
        )
        assert response.status_code == 422

    def test_public_apply_invalid_email(self, client, sample_job):
        """Test that invalid email returns 422."""
        response = client.get(f"/api/jobs/{sample_job['id']}", headers=sample_job["headers"])
        job = response.json()
        public_id = job["public_id"]

        files = {"resume": ("resume.pdf", b"content", "application/pdf")}
        data = {"name": "John Doe", "email": "not-an-email"}
        response = client.post(
            f"/api/public/apply/{public_id}",
            data=data,
            files=files,
        )
        assert response.status_code == 422

    def test_public_apply_numeric_id(self, client, sample_job):
        """Test that numeric job id also works for backward compatibility."""
        files = {"resume": ("resume.pdf", b"content", "application/pdf")}
        data = {"name": "Jane Smith", "email": "jane@example.com"}
        response = client.post(
            f"/api/public/apply/{sample_job['id']}",
            data=data,
            files=files,
        )
        assert response.status_code == 201
        body = response.json()
        assert body["name"] == "Jane Smith"
        assert body["job_id"] == sample_job["id"]