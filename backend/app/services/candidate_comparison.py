"""Comparative candidate analysis service.

Calculates relative competitiveness metrics by comparing candidates within the
same job based on their AI analysis results. This is a SEPARATE dimension from
the requirements fit score (match_percentage) that each candidate receives
independently.

Key principles:
--------------
1. Comparison is ALWAYS within the same job (never across different jobs).
2. Only candidates with completed AI analysis are included in the comparison pool.
3. Comparison uses only JOB-RELEVANT factors from the AI analysis.
4. NO protected/sensitive characteristics (gender, race, age, etc.) are used.
5. Percentile is dynamic and recalculated as the candidate pool changes.
6. This provides DECISION SUPPORT information only - HR makes the final decision.

Comparison factors:
-------------------
- Requirements fit score (match_percentage)
- Number of matched requirements vs total requirements
- Matched skills count
- Relevant experience count
- Overall analysis quality indicators

The comparison does NOT attempt to rank candidates definitively, but rather
provides context about where a candidate stands relative to others who have
applied to the same position.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models.application import AnalysisStatus, Application

logger = logging.getLogger(__name__)


class CandidateComparison:
    """Relative competitiveness metrics for one candidate within their job's pool."""

    def __init__(
        self,
        *,
        application_id: int,
        job_id: int,
        requirements_fit_score: float,
        relative_percentile: float,
        comparison_pool_size: int,
        rank: int,
        comparison_scope: str = "same_job",
    ):
        self.application_id = application_id
        self.job_id = job_id
        #: The candidate's independent requirements fit (0-100)
        self.requirements_fit_score = requirements_fit_score
        #: Percentile rank within the analyzed pool (0-100, higher is better)
        self.relative_percentile = relative_percentile
        #: Number of analyzed candidates in the comparison (including this one)
        self.comparison_pool_size = comparison_pool_size
        #: Ordinal rank (1 = highest score, 2 = second highest, etc.)
        self.rank = rank
        #: Always "same_job" to clarify comparison scope
        self.comparison_scope = comparison_scope

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return {
            "application_id": self.application_id,
            "job_id": self.job_id,
            "requirements_fit_score": round(self.requirements_fit_score, 2),
            "relative_percentile": round(self.relative_percentile, 2),
            "comparison_pool_size": self.comparison_pool_size,
            "rank": self.rank,
            "comparison_scope": self.comparison_scope,
        }


def calculate_candidate_comparison(
    db: Session,
    *,
    application_id: int,
    job_id: int,
    hr_user_id: int,
) -> CandidateComparison | None:
    """Calculate relative competitiveness for one candidate within their job pool.

    Args:
        db: Database session.
        application_id: The target application to compare.
        job_id: Job ID (verified for ownership).
        hr_user_id: HR user ID for ownership filtering.

    Returns:
        CandidateComparison if the application has been analyzed, None otherwise.

    Raises:
        ValueError if the application doesn't exist, doesn't belong to the job,
            or the user doesn't own the job.
    """
    # Fetch the target application with ownership check
    target_app = (
        db.query(Application)
        .join(Application.job)
        .filter(
            and_(
                Application.id == application_id,
                Application.job_id == job_id,
                Application.job.has(user_id=hr_user_id),
            )
        )
        .first()
    )

    if not target_app:
        raise ValueError(
            "Application not found or you do not have permission to access it."
        )

    # Can only compare analyzed applications
    if target_app.analysis_status != AnalysisStatus.COMPLETED:
        return None

    if target_app.ai_score is None:
        return None

    # Fetch ALL analyzed applications for this job (same owner)
    all_analyzed = (
        db.query(Application)
        .join(Application.job)
        .filter(
            and_(
                Application.job_id == job_id,
                Application.analysis_status == AnalysisStatus.COMPLETED,
                Application.ai_score.isnot(None),
                Application.job.has(user_id=hr_user_id),
            )
        )
        .order_by(Application.ai_score.desc())
        .all()
    )

    if not all_analyzed:
        return None

    pool_size = len(all_analyzed)
    
    # Sort by ai_score descending to determine rank
    scores = [app.ai_score for app in all_analyzed]
    scores.sort(reverse=True)
    
    # Find rank (1-based, 1 = highest score)
    target_score = target_app.ai_score
    rank = scores.index(target_score) + 1
    
    # Calculate percentile: percentage of candidates this candidate scores better than
    # If rank = 1 and pool = 10, percentile = 90 (better than 9 out of 9 others)
    # If rank = 10 and pool = 10, percentile = 0 (better than 0 out of 9 others)
    if pool_size == 1:
        percentile = 100.0
    else:
        percentile = ((pool_size - rank) / (pool_size - 1)) * 100

    return CandidateComparison(
        application_id=application_id,
        job_id=job_id,
        requirements_fit_score=target_app.ai_score,
        relative_percentile=percentile,
        comparison_pool_size=pool_size,
        rank=rank,
    )


def calculate_job_comparisons(
    db: Session,
    *,
    job_id: int,
    hr_user_id: int,
) -> list[CandidateComparison]:
    """Calculate relative metrics for ALL analyzed candidates in a job.

    Args:
        db: Database session.
        job_id: Job ID to analyze.
        hr_user_id: HR user ID for ownership filtering.

    Returns:
        List of CandidateComparison objects, one per analyzed application.
    """
    # Fetch all analyzed applications for this job
    all_analyzed = (
        db.query(Application)
        .join(Application.job)
        .filter(
            and_(
                Application.job_id == job_id,
                Application.analysis_status == AnalysisStatus.COMPLETED,
                Application.ai_score.isnot(None),
                Application.job.has(user_id=hr_user_id),
            )
        )
        .order_by(Application.ai_score.desc())
        .all()
    )

    if not all_analyzed:
        return []

    pool_size = len(all_analyzed)
    scores = [app.ai_score for app in all_analyzed]
    scores.sort(reverse=True)

    comparisons: list[CandidateComparison] = []

    for app in all_analyzed:
        rank = scores.index(app.ai_score) + 1
        
        if pool_size == 1:
            percentile = 100.0
        else:
            percentile = ((pool_size - rank) / (pool_size - 1)) * 100

        comparisons.append(
            CandidateComparison(
                application_id=app.id,
                job_id=job_id,
                requirements_fit_score=app.ai_score,
                relative_percentile=percentile,
                comparison_pool_size=pool_size,
                rank=rank,
            )
        )

    return comparisons
