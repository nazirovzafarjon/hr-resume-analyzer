"""Tests for candidate comparison service.

Tests the comparative analysis feature that calculates relative competitiveness
metrics for candidates within the same job.
"""

import pytest
from sqlalchemy.orm import Session

from app.models.application import AnalysisStatus, Application
from app.models.hr_account import HRAccount
from app.models.job import Job
from app.services.candidate_comparison import (
    CandidateComparison,
    calculate_candidate_comparison,
    calculate_job_comparisons,
)


@pytest.fixture
def hr_user(db: Session) -> HRAccount:
    """Create an HR user for testing."""
    user = HRAccount(
        email="hr@example.com",
        first_name="HR",
        last_name="User",
        hashed_password="fake_hash",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def other_hr_user(db: Session) -> HRAccount:
    """Create another HR user for ownership testing."""
    user = HRAccount(
        email="other@example.com",
        first_name="Other",
        last_name="HR",
        hashed_password="fake_hash",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def job(db: Session, hr_user: HRAccount) -> Job:
    """Create a test job."""
    job = Job(
        user_id=hr_user.id,
        company_name="Test Corp",
        position="Software Engineer",
        description="Test job",
        required_skills="Python, SQL",
        required_experience="3 years",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@pytest.fixture
def other_job(db: Session, other_hr_user: HRAccount) -> Job:
    """Create a job owned by a different HR user."""
    job = Job(
        user_id=other_hr_user.id,
        company_name="Other Corp",
        position="Developer",
        description="Other job",
        required_skills="Java",
        required_experience="2 years",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def create_analyzed_application(
    db: Session,
    job: Job,
    name: str,
    ai_score: float,
) -> Application:
    """Helper to create an analyzed application."""
    app = Application(
        job_id=job.id,
        name=name,
        email=f"{name.lower().replace(' ', '.')}@example.com",
        resume_path=f"/uploads/{name}.pdf",
        ai_score=ai_score,
        analysis_status=AnalysisStatus.COMPLETED,
        ai_analysis_details={
            "match_percentage": ai_score,
            "summary": f"Analysis for {name}",
            "matched_requirements": ["Python"],
            "missing_requirements": [],
            "matched_skills": ["Python"],
            "missing_skills": [],
            "strengths": ["Strong Python"],
            "weaknesses": [],
            "risks": [],
            "experience_analysis": "Good experience",
            "education_analysis": "Relevant degree",
            "relevant_experience": ["5 years Python"],
            "relevant_projects": ["Project X"],
            "ai_recommendation": "hire",
        },
    )
    db.add(app)
    db.commit()
    db.refresh(app)
    return app


def test_comparison_single_candidate(db: Session, hr_user: HRAccount, job: Job):
    """A single analyzed candidate should get 100th percentile."""
    app = create_analyzed_application(db, job, "Alice Smith", 85.0)

    comparison = calculate_candidate_comparison(
        db,
        application_id=app.id,
        job_id=job.id,
        hr_user_id=hr_user.id,
    )

    assert comparison is not None
    assert comparison.application_id == app.id
    assert comparison.job_id == job.id
    assert comparison.requirements_fit_score == 85.0
    assert comparison.relative_percentile == 100.0
    assert comparison.comparison_pool_size == 1
    assert comparison.rank == 1


def test_comparison_multiple_candidates(db: Session, hr_user: HRAccount, job: Job):
    """Multiple candidates should be ranked correctly."""
    alice = create_analyzed_application(db, job, "Alice", 90.0)
    bob = create_analyzed_application(db, job, "Bob", 75.0)
    charlie = create_analyzed_application(db, job, "Charlie", 60.0)

    # Alice (highest score) should be 1st (100th percentile)
    alice_comp = calculate_candidate_comparison(
        db, application_id=alice.id, job_id=job.id, hr_user_id=hr_user.id
    )
    assert alice_comp is not None
    assert alice_comp.rank == 1
    assert alice_comp.relative_percentile == 100.0
    assert alice_comp.comparison_pool_size == 3

    # Bob (middle score) should be 2nd (50th percentile)
    bob_comp = calculate_candidate_comparison(
        db, application_id=bob.id, job_id=job.id, hr_user_id=hr_user.id
    )
    assert bob_comp is not None
    assert bob_comp.rank == 2
    assert bob_comp.relative_percentile == 50.0
    assert bob_comp.comparison_pool_size == 3

    # Charlie (lowest score) should be 3rd (0th percentile)
    charlie_comp = calculate_candidate_comparison(
        db, application_id=charlie.id, job_id=job.id, hr_user_id=hr_user.id
    )
    assert charlie_comp is not None
    assert charlie_comp.rank == 3
    assert charlie_comp.relative_percentile == 0.0
    assert charlie_comp.comparison_pool_size == 3


def test_comparison_ignores_unanalyzed(db: Session, hr_user: HRAccount, job: Job):
    """Unanalyzed applications should not affect the comparison pool."""
    alice = create_analyzed_application(db, job, "Alice", 90.0)
    bob = create_analyzed_application(db, job, "Bob", 70.0)

    # Create unanalyzed application
    unanalyzed = Application(
        job_id=job.id,
        name="Unanalyzed",
        email="unanalyzed@example.com",
        resume_path="/uploads/unanalyzed.pdf",
        analysis_status=AnalysisStatus.NEW,
    )
    db.add(unanalyzed)
    db.commit()

    # Alice should still be 1st out of 2 (not 3)
    alice_comp = calculate_candidate_comparison(
        db, application_id=alice.id, job_id=job.id, hr_user_id=hr_user.id
    )
    assert alice_comp is not None
    assert alice_comp.comparison_pool_size == 2
    assert alice_comp.rank == 1


def test_comparison_unanalyzed_returns_none(db: Session, hr_user: HRAccount, job: Job):
    """Requesting comparison for unanalyzed application should return None."""
    app = Application(
        job_id=job.id,
        name="Unanalyzed",
        email="unanalyzed@example.com",
        resume_path="/uploads/test.pdf",
        analysis_status=AnalysisStatus.NEW,
    )
    db.add(app)
    db.commit()
    db.refresh(app)

    comparison = calculate_candidate_comparison(
        db,
        application_id=app.id,
        job_id=job.id,
        hr_user_id=hr_user.id,
    )

    assert comparison is None


def test_comparison_different_jobs_isolated(
    db: Session, hr_user: HRAccount, job: Job
):
    """Candidates from different jobs should not be compared."""
    # Job A
    alice = create_analyzed_application(db, job, "Alice", 90.0)

    # Job B (different position)
    job_b = Job(
        user_id=hr_user.id,
        company_name="Test Corp",
        position="Data Scientist",
        description="Different job",
        required_skills="Python, R",
        required_experience="5 years",
    )
    db.add(job_b)
    db.commit()
    db.refresh(job_b)

    bob = create_analyzed_application(db, job_b, "Bob", 95.0)

    # Alice should only be compared within Job A (pool size = 1)
    alice_comp = calculate_candidate_comparison(
        db, application_id=alice.id, job_id=job.id, hr_user_id=hr_user.id
    )
    assert alice_comp is not None
    assert alice_comp.comparison_pool_size == 1

    # Bob should only be compared within Job B (pool size = 1)
    bob_comp = calculate_candidate_comparison(
        db, application_id=bob.id, job_id=job_b.id, hr_user_id=hr_user.id
    )
    assert bob_comp is not None
    assert bob_comp.comparison_pool_size == 1


def test_comparison_ownership_enforced(
    db: Session, hr_user: HRAccount, other_hr_user: HRAccount, other_job: Job
):
    """HR user cannot access another user's application comparisons."""
    app = create_analyzed_application(db, other_job, "Alice", 90.0)

    with pytest.raises(ValueError, match="not found or you do not have permission"):
        calculate_candidate_comparison(
            db,
            application_id=app.id,
            job_id=other_job.id,
            hr_user_id=hr_user.id,  # Wrong user
        )


def test_comparison_invalid_application_raises_error(
    db: Session, hr_user: HRAccount, job: Job
):
    """Non-existent application should raise error."""
    with pytest.raises(ValueError, match="not found or you do not have permission"):
        calculate_candidate_comparison(
            db,
            application_id=99999,
            job_id=job.id,
            hr_user_id=hr_user.id,
        )


def test_job_comparisons_returns_all_analyzed(
    db: Session, hr_user: HRAccount, job: Job
):
    """Job comparisons should return all analyzed candidates."""
    alice = create_analyzed_application(db, job, "Alice", 90.0)
    bob = create_analyzed_application(db, job, "Bob", 75.0)
    charlie = create_analyzed_application(db, job, "Charlie", 60.0)

    # Create unanalyzed (should be excluded)
    unanalyzed = Application(
        job_id=job.id,
        name="Unanalyzed",
        email="unanalyzed@example.com",
        analysis_status=AnalysisStatus.NEW,
    )
    db.add(unanalyzed)
    db.commit()

    comparisons = calculate_job_comparisons(
        db, job_id=job.id, hr_user_id=hr_user.id
    )

    assert len(comparisons) == 3
    assert comparisons[0].application_id == alice.id
    assert comparisons[0].rank == 1
    assert comparisons[1].application_id == bob.id
    assert comparisons[1].rank == 2
    assert comparisons[2].application_id == charlie.id
    assert comparisons[2].rank == 3


def test_job_comparisons_empty_returns_empty_list(
    db: Session, hr_user: HRAccount, job: Job
):
    """Job with no analyzed candidates should return empty list."""
    comparisons = calculate_job_comparisons(
        db, job_id=job.id, hr_user_id=hr_user.id
    )

    assert comparisons == []


def test_comparison_to_dict(db: Session, hr_user: HRAccount, job: Job):
    """CandidateComparison.to_dict() should return serializable dict."""
    app = create_analyzed_application(db, job, "Alice", 87.5)

    comparison = calculate_candidate_comparison(
        db,
        application_id=app.id,
        job_id=job.id,
        hr_user_id=hr_user.id,
    )

    assert comparison is not None
    data = comparison.to_dict()

    assert isinstance(data, dict)
    assert data["application_id"] == app.id
    assert data["job_id"] == job.id
    assert data["requirements_fit_score"] == 87.5
    assert data["relative_percentile"] == 100.0
    assert data["comparison_pool_size"] == 1
    assert data["rank"] == 1
    assert data["comparison_scope"] == "same_job"


def test_comparison_same_scores_same_rank(db: Session, hr_user: HRAccount, job: Job):
    """Candidates with same score should get the same rank."""
    alice = create_analyzed_application(db, job, "Alice", 85.0)
    bob = create_analyzed_application(db, job, "Bob", 85.0)

    alice_comp = calculate_candidate_comparison(
        db, application_id=alice.id, job_id=job.id, hr_user_id=hr_user.id
    )
    bob_comp = calculate_candidate_comparison(
        db, application_id=bob.id, job_id=job.id, hr_user_id=hr_user.id
    )

    # Both should have rank 1 (tied for first)
    assert alice_comp is not None
    assert bob_comp is not None
    assert alice_comp.rank == 1
    assert bob_comp.rank == 1
