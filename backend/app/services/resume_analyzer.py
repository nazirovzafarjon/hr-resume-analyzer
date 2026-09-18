"""Resume analysis business logic and AI integration.

The current implementations are deterministic, keyword-based heuristics so the
application is fully functional without external AI providers. Swap the bodies
of ``analyze_resume`` and ``score_candidate`` for real LLM calls in production.
"""

import re

from sqlalchemy.orm import Session

from app.crud import worker as worker_crud
from app.models.worker import HiringStatus, Worker
from app.schemas.analysis import AnalysisResult, SkillMatch
from app.schemas.worker import WorkerUpdate


def _extract_skills(requirements: str) -> list[str]:
    """Split a free-text requirement list into individual, trimmed skills."""
    parts = re.split(r"[,;\n]+", requirements)
    return [part.strip() for part in parts if part.strip()]


def analyze_resume(resume_text: str, job_requirements: str) -> AnalysisResult:
    """Compare a resume against the job's required skills and score the match.

    ``score`` is the percentage of required skills present in the resume.
    Matching is case-insensitive and substring based.

    Args:
        resume_text: The plain-text resume content to analyse.
        job_requirements: A free-text list of required skills.
    """
    resume_lower = resume_text.lower()
    skill_matches = [
        SkillMatch(skill=skill, found=skill.lower() in resume_lower)
        for skill in _extract_skills(job_requirements)
    ]

    matched_skills = [match.skill for match in skill_matches if match.found]
    missing_skills = [match.skill for match in skill_matches if not match.found]

    total = len(skill_matches)
    score = round((len(matched_skills) / total) * 100, 2) if total else 0.0

    return AnalysisResult(
        score=score,
        matched_skills=matched_skills,
        missing_skills=missing_skills,
        skill_matches=skill_matches,
        summary=_build_summary(matched_skills, missing_skills, score),
    )


def _build_summary(
    matched_skills: list[str], missing_skills: list[str], score: float
) -> str:
    """Compose a human-readable summary for an analysis result."""
    if score >= 75:
        tone = "strong match"
    elif score >= 50:
        tone = "moderate match"
    else:
        tone = "weak match"

    parts = [f"{tone} with {score:.0f}% of required skills covered."]
    if missing_skills:
        parts.append(f"Missing: {', '.join(missing_skills)}.")
    return " ".join(parts)


def score_candidate(match_details: AnalysisResult) -> HiringStatus:
    """Map an analysis score to a concrete hiring recommendation."""
    if match_details.score >= 80:
        return HiringStatus.STRONG_HIRE
    if match_details.score >= 60:
        return HiringStatus.HIRE
    if match_details.score >= 40:
        return HiringStatus.WEAK_HIRE
    return HiringStatus.DO_NOT_HIRE


def analyze_and_update_worker(
    db: Session,
    worker: Worker,
    *,
    resume_text: str,
    job_requirements: str,
) -> Worker:
    """Run the resume analysis and persist the results onto the worker.

    Saves ``ai_score``, the full ``ai_analysis_details`` payload (matched
    skills, missing skills, per-skill matches and summary) and the
    auto-recommended ``hiring_status`` back to the :class:`Worker` record, then
    returns the refreshed instance.

    Args:
        db: Active database session.
        worker: The candidate application being scored.
        resume_text: Plain-text resume content to compare against the job.
        job_requirements: The job's required-skills list (free text).
    """
    result = analyze_resume(resume_text, job_requirements)
    payload = WorkerUpdate(
        ai_score=result.score,
        ai_analysis_details=result.model_dump(mode="json"),
        hiring_status=score_candidate(result),
    )
    return worker_crud.update_worker(db, worker, payload)