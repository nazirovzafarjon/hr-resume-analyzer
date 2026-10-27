"""Tests for application/candidate endpoints and application CRUD functions.

Applications belong to a job owned by the authenticated HR user. Other users'
applications behave like "not found" (no existence/ownership details leak).
"""

import pytest

from tests.payloads import APPLICATION_PAYLOAD

from app.crud import application as application_crud
from app.models.application import AnalysisStatus, Application, HiringStatus, InterviewStatus
from app.schemas.application import ApplicationCreate, ApplicationUpdate


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


class TestCreateApplication:
    def test_create_application_success(self, client, application_factory, sample_job):
        response = application_factory(sample_job["id"])
        assert response.status_code == 201
        body = response.json()
        assert body["name"] == "Jane Doe"
        assert body["job_id"] == sample_job["id"]
        assert body["hiring_status"] == "hire"
        assert body["interview_status"] == "not_completed"

    def test_create_application_increments_leads_count(self, client, application_factory, sample_job):
        application_factory(sample_job["id"])
        application_factory(sample_job["id"])
        job = client.get(f"/api/jobs/{sample_job['id']}", headers=sample_job["headers"]).json()
        assert job["leads_count"] == 2

    def test_create_application_for_unowned_job_returns_404(self, client, sample_job, other_user):
        response = client.post(
            f"/api/applications?job_id={sample_job['id']}",
            json=APPLICATION_PAYLOAD,
            headers=other_user["headers"],
        )
        assert response.status_code == 404

    def test_create_application_requires_job_id_param(self, client, user):
        response = client.post("/api/applications", json=APPLICATION_PAYLOAD, headers=user["headers"])
        assert response.status_code == 422

    def test_create_application_requires_auth(self, client, sample_job):
        response = client.post(f"/api/applications?job_id={sample_job['id']}", json=APPLICATION_PAYLOAD)
        assert response.status_code == 401

    def test_create_application_with_empty_name(self, client, application_factory, sample_job):
        payload = dict(APPLICATION_PAYLOAD, name="")
        assert application_factory(sample_job["id"], payload=payload).status_code == 422


# ---------------------------------------------------------------------------
# Read / list
# ---------------------------------------------------------------------------


class TestListApplications:
    def test_list_applications_for_job(self, client, application_factory, sample_job):
        application_factory(sample_job["id"])
        application_factory(sample_job["id"], payload=dict(APPLICATION_PAYLOAD, name="Bob Smith"))
        response = client.get(f"/api/applications?job_id={sample_job['id']}", headers=sample_job["headers"])
        assert response.status_code == 200
        assert {application["name"] for application in response.json()} == {"Jane Doe", "Bob Smith"}

    def test_list_applications_for_unowned_job_returns_404(self, client, sample_job, other_user):
        response = client.get(f"/api/applications?job_id={sample_job['id']}", headers=other_user["headers"])
        assert response.status_code == 404

    def test_list_applications_without_job_id_param_returns_all_owned(self, client, application_factory, sample_job):
        application_factory(sample_job["id"])
        application_factory(sample_job["id"], payload=dict(APPLICATION_PAYLOAD, name="Bob Smith"))
        response = client.get("/api/applications", headers=sample_job["headers"])
        assert response.status_code == 200
        assert {application["name"] for application in response.json()} == {"Jane Doe", "Bob Smith"}

    def test_list_applications_all_view_scoped_to_owner(self, client, application_factory, sample_job, other_user):
        application_factory(sample_job["id"])
        response = client.get("/api/applications", headers=other_user["headers"])
        assert response.status_code == 200
        assert response.json() == []

    def test_list_applications_filter_by_hiring_status(self, client, application_factory, sample_job):
        application_factory(sample_job["id"])
        weak = application_factory(sample_job["id"], payload=dict(APPLICATION_PAYLOAD, name="Weak Match"))
        assert client.patch(
            f"/api/applications/{weak.json()['id']}",
            json={"hiring_status": "weak_hire"},
            headers=sample_job["headers"],
        ).status_code == 200
        response = client.get(
            "/api/applications?hiring_status=weak_hire", headers=sample_job["headers"]
        )
        assert response.status_code == 200
        assert [application["name"] for application in response.json()] == ["Weak Match"]

    def test_list_applications_filter_by_interview_status(self, client, application_factory, sample_job):
        application_factory(sample_job["id"])
        done = application_factory(sample_job["id"], payload=dict(APPLICATION_PAYLOAD, name="Interviewed"))
        assert client.patch(
            f"/api/applications/{done.json()['id']}",
            json={"interview_status": "completed"},
            headers=sample_job["headers"],
        ).status_code == 200
        response = client.get(
            "/api/applications?interview_status=completed", headers=sample_job["headers"]
        )
        assert response.status_code == 200
        assert [application["name"] for application in response.json()] == ["Interviewed"]

    def test_list_applications_with_pagination(self, client, application_factory, sample_job):
        application_factory(sample_job["id"])
        application_factory(sample_job["id"], payload=dict(APPLICATION_PAYLOAD, name="Bob Smith"))
        response = client.get("/api/applications?skip=1&limit=1", headers=sample_job["headers"])
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_list_applications_invalid_hiring_status_returns_422(self, client, user):
        response = client.get("/api/applications?hiring_status=maybe", headers=user["headers"])
        assert response.status_code == 422
class TestGetApplication:
    def test_get_own_application(self, client, sample_application):
        response = client.get(f"/api/applications/{sample_application['id']}", headers=sample_application["headers"])
        assert response.status_code == 200
        assert response.json()["name"] == "Jane Doe"

    def test_get_application_from_other_users_job_returns_404(self, client, sample_application, other_user):
        response = client.get(f"/api/applications/{sample_application['id']}", headers=other_user["headers"])
        assert response.status_code == 404

    def test_get_missing_application_returns_404(self, client, user):
        assert client.get("/api/applications/999999", headers=user["headers"]).status_code == 404


# ---------------------------------------------------------------------------
# Update (PATCH): hiring / interview status
# ---------------------------------------------------------------------------


class TestUpdateApplication:
    def test_update_hiring_status(self, client, sample_application):
        response = client.patch(
            f"/api/applications/{sample_application['id']}",
            json={"hiring_status": "strong_hire"},
            headers=sample_application["headers"],
        )
        assert response.status_code == 200
        assert response.json()["hiring_status"] == "strong_hire"
        assert response.json()["interview_status"] == "not_completed"  # untouched

    def test_update_interview_status(self, client, sample_application):
        response = client.patch(
            f"/api/applications/{sample_application['id']}",
            json={"interview_status": "completed"},
            headers=sample_application["headers"],
        )
        assert response.status_code == 200
        assert response.json()["interview_status"] == "completed"

    def test_update_with_invalid_hiring_status(self, client, sample_application):
        response = client.patch(
            f"/api/applications/{sample_application['id']}",
            json={"hiring_status": "maybe"},
            headers=sample_application["headers"],
        )
        assert response.status_code == 422

    def test_update_with_invalid_interview_status(self, client, sample_application):
        response = client.patch(
            f"/api/applications/{sample_application['id']}",
            json={"interview_status": "almost_done"},
            headers=sample_application["headers"],
        )
        assert response.status_code == 422

    def test_update_other_users_application_returns_404(self, client, sample_application, other_user):
        response = client.patch(
            f"/api/applications/{sample_application['id']}",
            json={"hiring_status": "hire"},
            headers=other_user["headers"],
        )
        assert response.status_code == 404

    def test_update_missing_application_returns_404(self, client, user):
        response = client.patch("/api/applications/999999", json={"hiring_status": "hire"}, headers=user["headers"])
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Analyze: AI screening result persisted onto the application
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


class TestAnalyzeApplication:
    def test_analyze_saves_score_details_and_recommendation(self, client, sample_application):
        from unittest.mock import AsyncMock, patch
        from app.schemas.application_analysis import ApplicationAnalysis

        mock_result = ApplicationAnalysis(**SAMPLE_ANALYSIS_DATA)
        with patch(
            "app.services.application_analysis.analyze_application",
            new_callable=AsyncMock,
        ) as mock_analyze:
            mock_analyze.return_value = mock_result
            response = client.post(
                f"/api/applications/{sample_application['id']}/analyze",
                headers=sample_application["headers"],
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

    def test_analyze_without_force_skips_if_completed(self, client, sample_application):
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
                f"/api/applications/{sample_application['id']}/analyze",
                headers=sample_application["headers"],
            )
            assert mock_analyze.call_count == 1

            # Second run without force=True should not re-trigger AI:
            client.post(
                f"/api/applications/{sample_application['id']}/analyze",
                headers=sample_application["headers"],
            )
            assert mock_analyze.call_count == 1

    def test_analyze_failure_persists_error_and_keeps_application(self, client, sample_application):
        from unittest.mock import AsyncMock, patch
        from app.services.ai.job_analyzer import AIServiceError

        with patch(
            "app.services.application_analysis.analyze_application",
            new_callable=AsyncMock,
        ) as mock_analyze:
            mock_analyze.side_effect = AIServiceError("OpenRouter rate limit exceeded", status_code=429)
            response = client.post(
                f"/api/applications/{sample_application['id']}/analyze?force=true",
                headers=sample_application["headers"],
            )
        # Endpoint returns the application with failed analysis status so UI can show retry:
        assert response.status_code == 200
        body = response.json()
        assert body["analysis_status"] == "failed"
        assert "OpenRouter rate limit" in body["analysis_error"]
        # Application itself was not deleted:
        get_res = client.get(f"/api/applications/{sample_application['id']}", headers=sample_application["headers"])
        assert get_res.status_code == 200
        assert get_res.json()["name"] == "Jane Doe"

    def test_analyze_other_users_application_returns_404(self, client, sample_application, other_user):
        response = client.post(
            f"/api/applications/{sample_application['id']}/analyze",
            headers=other_user["headers"],
        )
        assert response.status_code == 404

    def test_analyze_missing_application_returns_404(self, client, user):
        response = client.post(
            "/api/applications/999999/analyze",
            headers=user["headers"],
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Convert to candidate & Candidate pipeline
# ---------------------------------------------------------------------------


class TestConvertToCandidate:
    def test_convert_to_candidate_success(self, client, sample_application):
        response = client.post(
            f"/api/applications/{sample_application['id']}/convert-to-candidate",
            headers=sample_application["headers"],
        )
        assert response.status_code == 200
        body = response.json()
        assert body["is_candidate"] is True
        assert body["candidate_at"] is not None

    def test_convert_to_candidate_idempotent(self, client, sample_application):
        res1 = client.post(
            f"/api/applications/{sample_application['id']}/convert-to-candidate",
            headers=sample_application["headers"],
        )
        res2 = client.post(
            f"/api/applications/{sample_application['id']}/convert-to-candidate",
            headers=sample_application["headers"],
        )
        assert res1.status_code == 200
        assert res2.status_code == 200
        assert res1.json()["candidate_at"] == res2.json()["candidate_at"]

    def test_convert_to_candidate_unowned_returns_404(self, client, sample_application, other_user):
        response = client.post(
            f"/api/applications/{sample_application['id']}/convert-to-candidate",
            headers=other_user["headers"],
        )
        assert response.status_code == 404

    def test_candidate_only_filter(self, client, application_factory, sample_job):
        w1 = application_factory(sample_job["id"]).json()
        w2 = application_factory(sample_job["id"], payload=dict(APPLICATION_PAYLOAD, name="Candidate Two")).json()

        # Convert w2 to candidate:
        client.post(
            f"/api/applications/{w2['id']}/convert-to-candidate",
            headers=sample_job["headers"],
        )

        # Listing with candidate_only=true returns only w2:
        res = client.get("/api/applications?candidate_only=true", headers=sample_job["headers"])
        assert res.status_code == 200
        items = res.json()
        assert len(items) == 1
        assert items[0]["id"] == w2["id"]


# ---------------------------------------------------------------------------
# Stored Analysis GET endpoint
# ---------------------------------------------------------------------------


class TestApplicationAnalysisEndpoint:
    def test_get_application_analysis_returns_stored_data(self, client, sample_application):
        from unittest.mock import AsyncMock, patch
        from app.schemas.application_analysis import ApplicationAnalysis

        mock_result = ApplicationAnalysis(**SAMPLE_ANALYSIS_DATA)
        with patch(
            "app.services.application_analysis.analyze_application",
            new_callable=AsyncMock,
        ) as mock_analyze:
            mock_analyze.return_value = mock_result
            client.post(
                f"/api/applications/{sample_application['id']}/analyze",
                headers=sample_application["headers"],
            )

        # GET /api/applications/{id}/analysis should read stored data:
        response = client.get(
            f"/api/applications/{sample_application['id']}/analysis",
            headers=sample_application["headers"],
        )
        assert response.status_code == 200
        body = response.json()
        assert body["application_id"] == sample_application["id"]
        assert body["analysis_status"] == "completed"
        assert body["ai_score"] == 92.5
        assert body["analysis"]["match_percentage"] == 92.5
        assert body["analysis"]["ai_recommendation"] == "strong_hire"

    def test_get_application_analysis_unowned_returns_404(self, client, sample_application, other_user):
        response = client.get(
            f"/api/applications/{sample_application['id']}/analysis",
            headers=other_user["headers"],
        )
        assert response.status_code == 404



# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


class TestDeleteApplication:
    def test_delete_application_success(self, client, sample_application):
        response = client.delete(f"/api/applications/{sample_application['id']}", headers=sample_application["headers"])
        assert response.status_code == 204
        missing = client.get(f"/api/applications/{sample_application['id']}", headers=sample_application["headers"])
        assert missing.status_code == 404

    def test_delete_other_users_application_returns_404(self, client, sample_application, other_user):
        response = client.delete(f"/api/applications/{sample_application['id']}", headers=other_user["headers"])
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Application CRUD functions
# ---------------------------------------------------------------------------


class TestApplicationCrud:
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

    def test_create_application(self, db_session):
        owner = self._create_owner(db_session)
        job = self._create_job_with_owner(db_session, owner.id)
        application = application_crud.create_application(db_session, job_id=job.id, payload=ApplicationCreate(**APPLICATION_PAYLOAD))
        assert application.id is not None
        assert application.job_id == job.id
        assert application.hiring_status == HiringStatus.HIRE
        assert application.interview_status == InterviewStatus.NOT_COMPLETED

    def test_get_application(self, db_session):
        owner = self._create_owner(db_session)
        job = self._create_job_with_owner(db_session, owner.id)
        application = application_crud.create_application(db_session, job_id=job.id, payload=ApplicationCreate(**APPLICATION_PAYLOAD))
        assert application_crud.get_application(db_session, application.id) is application
        assert application_crud.get_application(db_session, 999999) is None

    def test_get_applications_for_job_filters_by_job(self, db_session):
        owner = self._create_owner(db_session)
        job_a = self._create_job_with_owner(db_session, owner.id, position="Dev")
        job_b = self._create_job_with_owner(db_session, owner.id, position="QA")
        application_crud.create_application(db_session, job_id=job_a.id, payload=ApplicationCreate(**APPLICATION_PAYLOAD))
        application_crud.create_application(db_session, job_id=job_b.id, payload=ApplicationCreate(**APPLICATION_PAYLOAD))
        applications = application_crud.get_applications_for_job(db_session, job_id=job_a.id)
        assert len(applications) == 1
        assert applications[0].job_id == job_a.id

    def test_list_applications_scopes_to_owner_and_filters(self, db_session):
        owner = self._create_owner(db_session)
        other = self._create_owner(db_session, email="other@example.com")
        job = self._create_job_with_owner(db_session, owner.id, position="Dev")
        other_job = self._create_job_with_owner(db_session, other.id, position="QA")
        strong = application_crud.create_application(db_session, job_id=job.id, payload=ApplicationCreate(**APPLICATION_PAYLOAD))
        application_crud.create_application(db_session, job_id=job.id, payload=ApplicationCreate(**{**APPLICATION_PAYLOAD, "name": "Second"}))
        application_crud.create_application(db_session, job_id=other_job.id, payload=ApplicationCreate(**{**APPLICATION_PAYLOAD, "name": "Foreign"}))

        all_owned = application_crud.list_applications(db_session, owner.id)
        assert {w.name for w in all_owned} == {"Jane Doe", "Second"}

        filtered = application_crud.list_applications(db_session, owner.id, hiring_status=HiringStatus.HIRE)
        assert len(filtered) == 2

        application_crud.update_application(db_session, strong, ApplicationUpdate(hiring_status=HiringStatus.STRONG_HIRE))
        filtered = application_crud.list_applications(db_session, owner.id, hiring_status=HiringStatus.STRONG_HIRE)
        assert [w.id for w in filtered] == [strong.id]

        by_job = application_crud.list_applications(db_session, owner.id, job_id=job.id)
        assert all(w.job_id == job.id for w in by_job)

    def test_list_applications_paginates(self, db_session):
        owner = self._create_owner(db_session)
        job = self._create_job_with_owner(db_session, owner.id, position="Dev")
        for name in ("One", "Two", "Three"):
            application_crud.create_application(
                db_session, job_id=job.id, payload=ApplicationCreate(**{**APPLICATION_PAYLOAD, "name": name})
            )
        page = application_crud.list_applications(db_session, owner.id, skip=1, limit=2)
        assert len(page) == 2
        # Ordered by created_at desc: newest first.
        assert [w.name for w in page] == ["Two", "One"]

    def test_get_recent_applications_across_owners_jobs(self, db_session):
        owner_a = self._create_owner(db_session, email="owner-a@example.com")
        owner_b = self._create_owner(db_session, email="owner-b@example.com")
        job_a = self._create_job_with_owner(db_session, owner_a.id, position="Dev")
        job_b = self._create_job_with_owner(db_session, owner_b.id, position="QA")

        application_crud.create_application(db_session, job_id=job_a.id, payload=ApplicationCreate(**APPLICATION_PAYLOAD))
        application_crud.create_application(db_session, job_id=job_b.id, payload=ApplicationCreate(**APPLICATION_PAYLOAD))

        recent = application_crud.get_recent_applications(db_session, owner_id=owner_a.id, limit=5)
        assert [w.job_id for w in recent] == [job_a.id]
        # The job is eagerly loaded with the application (no lazy-load crash).
        assert recent[0].job.company_name == "Acme Corp"

    def test_update_application_applies_only_submitted_fields(self, db_session):
        owner = self._create_owner(db_session)
        job = self._create_job_with_owner(db_session, owner.id)
        application = application_crud.create_application(db_session, job_id=job.id, payload=ApplicationCreate(**APPLICATION_PAYLOAD))
        updated = application_crud.update_application(db_session, application, ApplicationUpdate(hiring_status=HiringStatus.STRONG_HIRE))
        assert updated.hiring_status == HiringStatus.STRONG_HIRE
        assert updated.interview_status == InterviewStatus.NOT_COMPLETED  # untouched

    def test_delete_application(self, db_session):
        owner = self._create_owner(db_session)
        job = self._create_job_with_owner(db_session, owner.id)
        application = application_crud.create_application(db_session, job_id=job.id, payload=ApplicationCreate(**APPLICATION_PAYLOAD))
        application_crud.delete_application(db_session, application.id)
        assert application_crud.get_application(db_session, application.id) is None


# ---------------------------------------------------------------------------
# Application Comparison (Relative Competitiveness) API Tests
# ---------------------------------------------------------------------------


class TestApplicationComparisonAPI:
    """Regression tests for the Application Comparison feature.
    
    These tests ensure the comparison endpoint works correctly after fixing
    the AttributeError bug where SQLAlchemy queries incorrectly used
    Job.user_id instead of Job.owner_id.
    
    The bug manifested as:
        AttributeError: type object 'Job' has no attribute 'user_id'. 
        Did you mean: 'owner_id'?
    
    These tests verify:
    1. The endpoint returns 200 (not 500) for valid requests
    2. Ownership filtering uses the correct Job.owner_id field
    3. HR users cannot access other users' application comparisons
    4. Unanalyzed applications return appropriate response
    """

    @pytest.fixture
    def analyzed_application(self, sample_application, db_session):
        """Mark the sample application as AI-analyzed with a completed score."""
        application = db_session.get(Application, sample_application["id"])
        application.analysis_status = AnalysisStatus.COMPLETED
        application.ai_score = 82.5
        application.ai_analysis_details = {"match_percentage": 82.5}
        db_session.commit()
        return sample_application

    def test_get_comparison_for_analyzed_application_succeeds(
        self, client, sample_job, analyzed_application
    ):
        """Valid owner can access comparison for analyzed application.
        
        Regression test: This should return 200, not 500 AttributeError.
        """
        response = client.get(
            f"/api/applications/{analyzed_application['id']}/comparison",
            headers=sample_job["headers"],
        )
        assert response.status_code == 200
        body = response.json()
        assert body["has_comparison"] is True
        assert body["application_id"] == analyzed_application["id"]
        assert body["job_id"] == sample_job["id"]
        assert "requirements_fit_score" in body
        assert "relative_percentile" in body
        assert "comparison_pool_size" in body
        assert "rank" in body
        assert body["comparison_scope"] == "same_job"

    def test_get_comparison_for_unanalyzed_application_returns_no_comparison(
        self, client, sample_job, application_factory
    ):
        """Unanalyzed applications return has_comparison: false."""
        app_response = application_factory(sample_job["id"])
        app_id = app_response.json()["id"]

        response = client.get(
            f"/api/applications/{app_id}/comparison",
            headers=sample_job["headers"],
        )
        assert response.status_code == 200
        body = response.json()
        assert body["has_comparison"] is False
        assert "reason" in body

    def test_get_comparison_for_other_users_application_returns_404(
        self, client, sample_job, analyzed_application, other_user
    ):
        """HR user cannot access another user's application comparison.
        
        Ensures ownership filtering works correctly with Job.owner_id.
        """
        response = client.get(
            f"/api/applications/{analyzed_application['id']}/comparison",
            headers=other_user["headers"],
        )
        assert response.status_code == 404

    def test_get_comparison_requires_authentication(
        self, client, analyzed_application
    ):
        """Comparison endpoint requires authentication."""
        response = client.get(
            f"/api/applications/{analyzed_application['id']}/comparison"
        )
        assert response.status_code == 401

    def test_get_job_comparisons_returns_all_analyzed(
        self, client, sample_job, analyzed_application
    ):
        """Job comparisons endpoint returns all analyzed applications for a job."""
        response = client.get(
            f"/api/applications/jobs/{sample_job['id']}/comparisons",
            headers=sample_job["headers"],
        )
        assert response.status_code == 200
        body = response.json()
        assert body["job_id"] == sample_job["id"]
        assert body["total_analyzed"] >= 1
        assert "comparisons" in body
        assert isinstance(body["comparisons"], list)

    def test_get_job_comparisons_for_other_users_job_returns_404(
        self, client, sample_job, other_user
    ):
        """HR user cannot access another user's job comparisons."""
        response = client.get(
            f"/api/applications/jobs/{sample_job['id']}/comparisons",
            headers=other_user["headers"],
        )
        assert response.status_code == 404
