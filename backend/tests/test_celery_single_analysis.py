"""Tests for Celery single application AI analysis task."""

from unittest.mock import AsyncMock, patch
import pytest

from app.models.application import AnalysisStatus, Application
from app.schemas.application_analysis import ApplicationAnalysis
from app.services.ai.job_analyzer import AIServiceError
from app.tasks.ai_analysis import analyze_single_application_task

SAMPLE_RESULT = {
    "match_percentage": 91.0,
    "summary": "Strong candidate for backend developer role.",
    "matched_requirements": ["Python", "FastAPI"],
    "missing_requirements": [],
    "matched_skills": ["Python", "PostgreSQL"],
    "missing_skills": [],
    "strengths": ["Solid experience in REST APIs"],
    "weaknesses": [],
    "risks": [],
    "experience_analysis": "3+ years backend experience.",
    "education_analysis": "Relevant CS degree.",
    "relevant_experience": ["Backend Engineer at TechCorp"],
    "relevant_projects": ["Microservice migration"],
    "ai_recommendation": "strong_hire",
}


def test_celery_single_analysis_task_success(client, sample_application, db_session):
    """Test successful execution of analyze_single_application_task."""
    mock_analysis = ApplicationAnalysis(**SAMPLE_RESULT)

    with patch(
        "app.services.application_analysis.analyze_application",
        new_callable=AsyncMock,
    ) as mock_analyze:
        mock_analyze.return_value = mock_analysis

        result = analyze_single_application_task.apply(
            kwargs={"application_id": sample_application["id"], "force": False}
        ).result

    assert result["status"] == "completed"
    assert result["application_id"] == sample_application["id"]
    assert result["score"] == 91.0

    app = db_session.get(Application, sample_application["id"])
    assert app.analysis_status == AnalysisStatus.COMPLETED
    assert app.ai_score == 91.0
    assert app.ai_analysis_details is not None
    assert app.ai_analysis_details["ai_recommendation"] == "strong_hire"


def test_celery_single_analysis_idempotency(client, sample_application, db_session):
    """Test that completed analysis is not re-analyzed unless force=True."""
    mock_analysis = ApplicationAnalysis(**SAMPLE_RESULT)

    with patch(
        "app.services.application_analysis.analyze_application",
        new_callable=AsyncMock,
    ) as mock_analyze:
        mock_analyze.return_value = mock_analysis

        # First run
        res1 = analyze_single_application_task.apply(
            kwargs={"application_id": sample_application["id"], "force": False}
        ).result
        assert res1["status"] == "completed"
        assert mock_analyze.call_count == 1

        # Second run without force should return early
        res2 = analyze_single_application_task.apply(
            kwargs={"application_id": sample_application["id"], "force": False}
        ).result
        assert res2["status"] == "already_completed"
        assert mock_analyze.call_count == 1  # Not called again


def test_celery_single_analysis_force_rerun(client, sample_application, db_session):
    """Test that force=True re-analyzes even if already completed."""
    mock_analysis = ApplicationAnalysis(**SAMPLE_RESULT)

    with patch(
        "app.services.application_analysis.analyze_application",
        new_callable=AsyncMock,
    ) as mock_analyze:
        mock_analyze.return_value = mock_analysis

        # Initial run
        analyze_single_application_task.apply(
            kwargs={"application_id": sample_application["id"], "force": False}
        )
        assert mock_analyze.call_count == 1

        # Re-run with force=True
        res = analyze_single_application_task.apply(
            kwargs={"application_id": sample_application["id"], "force": True}
        ).result
        assert res["status"] == "completed"
        assert mock_analyze.call_count == 2


def test_celery_single_analysis_not_found(db_session):
    """Test task behavior with non-existent application ID."""
    result = analyze_single_application_task.apply(
        kwargs={"application_id": 999999, "force": False}
    ).result
    assert result["status"] == "not_found"


def test_celery_single_analysis_failure_handling(client, sample_application, db_session):
    """Test that permanent AI error marks application as failed in database."""
    with patch(
        "app.services.application_analysis.analyze_application",
        new_callable=AsyncMock,
    ) as mock_analyze:
        mock_analyze.side_effect = AIServiceError(
            "Unprocessable request payload", status_code=422
        )

        result = analyze_single_application_task.apply(
            kwargs={"application_id": sample_application["id"], "force": True}
        ).result

    assert result["status"] == "failed"
    assert "Unprocessable" in result["error"]

    db_session.expire_all()
    app = db_session.get(Application, sample_application["id"])
    assert app.analysis_status == AnalysisStatus.FAILED
    assert "Unprocessable" in app.analysis_error
