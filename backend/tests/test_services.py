"""Unit tests for business-logic services.

* ``app.services.ai.heuristic`` - keyword-based resume analysis heuristics.
* ``app.services.job`` - lead counting and analytics aggregation.
"""

import pytest

from app.models.worker import HiringStatus
from app.services.job import increment_leads_count, job_analytics
from app.services.ai.heuristic import (
    _extract_skills,
    analyze_resume,
    score_candidate,
)


# ---------------------------------------------------------------------------
# skill extraction
# ---------------------------------------------------------------------------


class TestExtractSkills:
    def test_splits_comma_separated_skills(self):
        assert _extract_skills("Python, FastAPI, SQL") == ["Python", "FastAPI", "SQL"]

    def test_splits_on_semicolons_newlines_and_commas(self):
        assert _extract_skills("Python; FastAPI\nSQL, Docker") == ["Python", "FastAPI", "SQL", "Docker"]

    def test_trims_whitespace_and_drops_empties(self):
        assert _extract_skills(" Python , ,  FastAPI \n") == ["Python", "FastAPI"]

    def test_empty_requirements_give_no_skills(self):
        assert _extract_skills("") == []


# ---------------------------------------------------------------------------
# analyze_resume
# ---------------------------------------------------------------------------


class TestAnalyzeResume:
    def test_perfect_match_scores_100(self):
        result = analyze_resume("Expert in Python and FastAPI.", "Python, FastAPI")
        assert result.score == 100.0
        assert result.matched_skills == ["Python", "FastAPI"]
        assert result.missing_skills == []

    def test_partial_match_scores_proportionally(self):
        result = analyze_resume("I know Python.", "Python, FastAPI, Docker")
        assert result.score == pytest.approx(33.33)
        assert result.matched_skills == ["Python"]
        assert result.missing_skills == ["FastAPI", "Docker"]

    def test_matching_is_case_insensitive(self):
        result = analyze_resume("I love python and FASTAPI.", "Python, FastAPI")
        assert result.matched_skills == ["Python", "FastAPI"]
        assert result.score == 100.0

    def test_matching_is_substring_based(self):
        # "sql" appears inside "PostgreSQL" and still counts.
        result = analyze_resume("PostgreSQL for storage.", "SQL")
        assert result.matched_skills == ["SQL"]
        assert result.score == 100.0

    def test_no_match_scores_zero(self):
        result = analyze_resume("I do marketing.", "Python, FastAPI")
        assert result.score == 0.0
        assert result.missing_skills == ["Python", "FastAPI"]

    def test_empty_requirements_score_zero(self):
        result = analyze_resume("Anything here.", "")
        assert result.score == 0.0
        assert result.matched_skills == []
        assert result.missing_skills == []
        assert result.skill_matches == []

    def test_summary_mentions_coverage_and_missing(self):
        result = analyze_resume("Python only.", "Python, FastAPI")
        assert "50% of required skills covered" in result.summary
        assert "Missing: FastAPI." in result.summary
# ---------------------------------------------------------------------------
# score_candidate
# ---------------------------------------------------------------------------


class TestScoreCandidate:
    def test_high_score_is_strong_hire(self):
        result = analyze_resume("Python, FastAPI, SQL, Docker", "Python, FastAPI, SQL, Docker")
        assert score_candidate(result) == HiringStatus.STRONG_HIRE

    def test_mid_range_score_is_hire(self):
        # 4 of 6 required => 66.7%, which falls in the "hire" band (>= 60).
        result = analyze_resume("python fastapi sql docker", "python, fastapi, sql, docker, git, redis")
        assert score_candidate(result) == HiringStatus.HIRE

    def test_low_range_score_is_weak_hire(self):
        # 2 of 5 required => 40%, which falls in the "weak_hire" band (>= 40).
        result = analyze_resume("python fastapi", "python, fastapi, sql, docker, git")
        assert score_candidate(result) == HiringStatus.WEAK_HIRE

    def test_zero_score_is_do_not_hire(self):
        result = analyze_resume("nothing relevant here", "Python, FastAPI")
        assert score_candidate(result) == HiringStatus.DO_NOT_HIRE


# ---------------------------------------------------------------------------
# job service: increment_leads_count
# ---------------------------------------------------------------------------


class TestIncrementLeadsCount:
    def test_increments_leads_count(self, db_session):
        from app.crud import user as user_crud
        from app.crud.job import create_job
        from app.schemas.job import JobCreate
        from app.schemas.user import UserCreate
        from tests.payloads import JOB_PAYLOAD

        owner = user_crud.create_user(
            db_session, UserCreate(email="owner@example.com", full_name="Owner", password="PassPass123")
        )
        job = create_job(db_session, owner_id=owner.id, payload=JobCreate(**JOB_PAYLOAD))
        increment_leads_count(db_session, job.id)
        assert increment_leads_count(db_session, job.id).leads_count == 2

    def test_missing_job_returns_none(self, db_session):
        assert increment_leads_count(db_session, 999999) is None
# ---------------------------------------------------------------------------
# job service: job_analytics
# ---------------------------------------------------------------------------


class TestJobAnalytics:
    def test_unsupported_category_raises(self, db_session):
        with pytest.raises(ValueError):
            job_analytics(db_session, owner_id=1, category="salary")

    def test_empty_database_returns_zeros(self, db_session):
        result = job_analytics(db_session, owner_id=1)
        assert result["total_jobs"] == 0
        assert result["total_candidates"] == 0
        assert result["total_leads"] == 0
        assert result["breakdown"] == []

    def test_aggregates_jobs_and_candidates(self, db_session):
        from app.crud import user as user_crud
        from app.crud.job import create_job
        from app.crud.worker import create_worker
        from app.schemas.job import JobCreate
        from app.schemas.user import UserCreate
        from app.schemas.worker import WorkerCreate
        from tests.payloads import JOB_PAYLOAD, WORKER_PAYLOAD

        owner_one = user_crud.create_user(
            db_session, UserCreate(email="one@example.com", full_name="One", password="PassPass123")
        )
        owner_two = user_crud.create_user(
            db_session, UserCreate(email="two@example.com", full_name="Two", password="PassPass123")
        )

        acme_backend = create_job(
            db_session,
            owner_id=owner_one.id,
            payload=JobCreate(**{**JOB_PAYLOAD, "company_name": "Acme", "position": "Backend"}),
        )
        acme_data = create_job(
            db_session,
            owner_id=owner_one.id,
            payload=JobCreate(**{**JOB_PAYLOAD, "company_name": "Acme", "position": "Data"}),
        )
        create_job(  # belongs to another owner - must be ignored
            db_session,
            owner_id=owner_two.id,
            payload=JobCreate(**{**JOB_PAYLOAD, "company_name": "Other", "position": "QA"}),
        )
        create_worker(db_session, acme_backend.id, WorkerCreate(**WORKER_PAYLOAD))
        create_worker(db_session, acme_backend.id, WorkerCreate(**{**WORKER_PAYLOAD, "name": "Second"}))
        create_worker(db_session, acme_data.id, WorkerCreate(**WORKER_PAYLOAD))

        result = job_analytics(db_session, owner_id=owner_one.id, category="company")

        assert result["total_jobs"] == 2  # only owner 1's jobs
        assert result["total_candidates"] == 3
        breakdown = {row["category"]: row for row in result["breakdown"]}
        assert breakdown["Acme"] == {"category": "Acme", "jobs": 2, "candidates": 3}
# ---------------------------------------------------------------------------
# resume analyzer service: analyze_and_update_worker
# ---------------------------------------------------------------------------


class TestAnalyzeAndUpdateWorker:
    def _seed(self, db_session):
        from app.crud import user as user_crud
        from app.crud.job import create_job
        from app.crud.worker import create_worker
        from app.schemas.job import JobCreate
        from app.schemas.user import UserCreate
        from app.schemas.worker import WorkerCreate
        from tests.payloads import JOB_PAYLOAD, WORKER_PAYLOAD

        owner = user_crud.create_user(
            db_session, UserCreate(email="owner@example.com", full_name="Owner", password="PassPass123")
        )
        job = create_job(db_session, owner_id=owner.id, payload=JobCreate(**JOB_PAYLOAD))
        worker = create_worker(db_session, job.id, WorkerCreate(**WORKER_PAYLOAD))
        return job, worker

    def test_persists_score_details_and_recommendation(self, db_session):
        from app.services.ai.heuristic import analyze_and_update_worker

        job, worker = self._seed(db_session)
        updated = analyze_and_update_worker(
            db_session,
            worker,
            resume_text="Expert in Python, FastAPI and PostgreSQL.",
            job_requirements=job.required_skills,
        )
        assert updated.ai_score == 100.0
        assert updated.hiring_status == HiringStatus.STRONG_HIRE
        assert updated.ai_analysis_details["matched_skills"] == [
            "Python",
            "FastAPI",
            "PostgreSQL",
        ]
        assert updated.ai_analysis_details["missing_skills"] == []
        assert updated.ai_analysis_details["skill_matches"][0] == {
            "skill": "Python",
            "found": True,
        }
        assert "strong match" in updated.ai_analysis_details["summary"]

        # Actually committed to the database, not just in memory.
        db_session.refresh(worker)
        assert worker.ai_score == 100.0
        assert worker.hiring_status == HiringStatus.STRONG_HIRE

    def test_overwrites_previous_analysis(self, db_session):
        from app.services.ai.heuristic import analyze_and_update_worker

        job, worker = self._seed(db_session)
        analyze_and_update_worker(
            db_session,
            worker,
            resume_text="Expert in Python, FastAPI and PostgreSQL.",
            job_requirements=job.required_skills,
        )
        re_analyzed = analyze_and_update_worker(
            db_session, worker, resume_text="I do marketing.", job_requirements=job.required_skills
        )
        assert re_analyzed.ai_score == 0.0
        assert re_analyzed.hiring_status == HiringStatus.DO_NOT_HIRE
        assert re_analyzed.ai_analysis_details["matched_skills"] == []
        assert re_analyzed.ai_analysis_details["missing_skills"] == ["Python", "FastAPI", "PostgreSQL"]