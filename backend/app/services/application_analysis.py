"""Application analysis and candidate-conversion business logic.

Responsibilities:

* Collect the analysis inputs for one application: the job's stored
  requirements, the answers submitted through the public form and the text
  extracted from the uploaded resume.
* Run the AI analysis and persist the structured result, tracking
  ``analysis_status``/``analysis_error`` so HR sees a retryable state when the
  provider fails.
* Read back the *stored* analysis (``GET`` requests never call the provider).
* Move an application into the candidate pipeline exactly once.

The AI never writes ``application_status``, ``hiring_status`` or
``interview_status`` — those stay under HR/interviewer control.
"""

import logging
import time
from datetime import datetime, timedelta, timezone

from pydantic import ValidationError
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.job import Job
from app.models.application import AnalysisStatus, Application
from app.schemas.application_analysis import ApplicationAnalysis
from app.services.ai.application_analyzer import analyze_application
from app.services.ai import monitoring as ai_monitoring
from app.services.ai import provider as ai_provider_service
from app.services import audit
from app.services.ai.job_analyzer import AIServiceError
from app.services.resume_text import extract_resume_text

logger = logging.getLogger(__name__)

#: A run that has been "analyzing" for longer than this counts as interrupted
#: (server restart, worker crash) and may be retried instead of blocking HR.
STALE_ANALYSIS_SECONDS = 600

#: Generic, user-safe message stored when an unexpected error occurs.
UNEXPECTED_FAILURE_MESSAGE = (
    "The analysis could not be completed. Please try again."
)


class AnalysisInProgressError(Exception):
    """Raised when an analysis run is already in flight for the application."""

    def __init__(
        self,
        message: str = "An analysis is already running for this application.",
        status_code: int = 409,
    ) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _utcnow() -> datetime:
    """Return the current UTC wall-clock time (timezone-aware)."""
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Analysis inputs (job + application form + resume)
# ---------------------------------------------------------------------------


def build_job_requirements(job: Job) -> str:
    """Render the job's stored requirement fields as prompt text.

    Only fields that actually exist on the job are used (company, position,
    description, required skills, required experience). Nothing is invented
    here — the AI receives exactly what HR saved on the vacancy.
    """
    lines: list[tuple[str, str]] = [
        ("Company", job.company_name or ""),
        ("Position", job.position or ""),
        ("Job description", job.description or ""),
        ("Required skills", job.required_skills or ""),
        ("Required experience", job.required_experience or ""),
    ]
    return "\n".join(f"{label}: {value}" for label, value in lines if value.strip())


def _format_value(value: object) -> str:
    """Render one submitted answer value as a single readable line."""
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value)


def build_form_answers(application: Application) -> str:
    """Render every answer the applicant submitted as ``Label: value`` lines.

    All submitted fields are included (the public form supports HR-authored
    custom questions), never only name/email/phone. Applications recorded
    manually by HR have no stored answers, so their identity fields are used
    instead.
    """
    response = application.application_response
    answers = (response.responses if response is not None else None) or []

    lines: list[str] = []
    for answer in answers:
        if not isinstance(answer, dict):
            continue
        label = str(answer.get("label") or answer.get("key") or "").strip()
        value = answer.get("value")
        if not label:
            continue
        rendered = _format_value(value).strip()
        lines.append(f"{label}: {rendered if rendered else '(not answered)'}")

    if not lines:
        # Manually recorded candidate: fall back to the identity fields.
        lines.append(f"Applicant name: {application.name}")
        lines.append(f"Applicant email: {application.email}")
    return "\n".join(lines)


def collect_analysis_inputs(application: Application) -> tuple[str, str, str, str | None]:
    """Return ``(job_requirements, form_answers, resume_text, resume_reason)``.

    ``resume_reason`` explains why no resume text is available (unsupported
    format, missing file, scanned PDF, ...) and is ``None`` when text was
    extracted.
    """
    resume = extract_resume_text(application.resume_path or "")
    return (
        build_job_requirements(application.job),
        build_form_answers(application),
        resume.text,
        resume.unavailable_reason,
    )
# ---------------------------------------------------------------------------
# Run + persist
# ---------------------------------------------------------------------------


def _is_run_active(application: Application) -> bool:
    """True when an analysis run is currently in flight (and not stale)."""
    if application.analysis_status != AnalysisStatus.ANALYZING:
        return False
    started = application.analysis_started_at
    if started is None:
        return True
    if started.tzinfo is None:  # Defensive: treat naive values as UTC.
        started = started.replace(tzinfo=timezone.utc)
    return _utcnow() - started < timedelta(seconds=STALE_ANALYSIS_SECONDS)


def _mark_failed(db: Session, application: Application, message: str | None) -> None:
    """Persist a failed analysis attempt (the application itself is kept)."""
    application.analysis_status = AnalysisStatus.FAILED
    application.analysis_error = (message or UNEXPECTED_FAILURE_MESSAGE)[:500]
    application.analysis_started_at = None
    db.commit()
    db.refresh(application)
    logger.warning(
        "Application analysis failed: application_id=%s reason=%s",
        application.id,
        application.analysis_error,
    )


def _record_outcome(
    db: Session,
    application: Application,
    owner_id: int,
    cfg: dict,
    started: float,
    *,
    score: float | None = None,
    error: BaseException | None = None,
) -> None:
    """Record the attempt for AI monitoring and the audit trail (best effort).

    The run row carries the diagnostics (provider, model, duration, error
    category); the audit row puts the outcome into the platform activity feed.
    Neither contains prompts, resume text or credentials.
    """
    ai_monitoring.record_run(
        db,
        kind=ai_monitoring.KIND_APPLICATION,
        cfg=cfg,
        duration_ms=round((time.monotonic() - started) * 1000),
        owner_id=owner_id,
        job_id=application.job_id,
        application_id=application.id,
        score=score,
        error=error,
    )
    audit.record(
        db,
        audit.AuditAction.AI_ANALYSIS_FAILED if error else audit.AuditAction.AI_ANALYSIS_COMPLETED,
        resource_type=audit.AuditResource.APPLICATION,
        resource_id=application.id,
        details={"job_id": application.job_id, "owner_id": owner_id, "score": score}
        if error is None
        else {"job_id": application.job_id, "owner_id": owner_id, "category": ai_monitoring.categorize(error)},
    )


async def run_analysis(db: Session, application: Application, *, force: bool = False) -> Application:
    """Analyse one application and store the structured result.

    The job requirements, the submitted form answers and the extracted resume
    text are sent to the configured AI provider. A provider failure is recorded
    as ``analysis_status="failed"`` with a safe message — the application and
    everything HR already has stay untouched and the run can be retried.

    Args:
        db: Active database session.
        application: The application/candidate being analysed.
        force: When ``False`` (default) an application that already has a stored
            analysis is returned as-is, so the provider is never called
            implicitly (page loads must not trigger AI).

    Raises:
        AnalysisInProgressError: A run is already in flight for this row.
        AIServiceError: The provider (or our validation) failed.
    """
    if (
        not force
        and application.analysis_status == AnalysisStatus.COMPLETED
        and application.ai_analysis_details
    ):
        logger.info(
            "Application already analysed -- skipping AI call: application_id=%s",
            application.id,
        )
        return application

    if _is_run_active(application):
        raise AnalysisInProgressError()

    # Credentials first (the job owner's; see app.services.ai.provider). With
    # no AI configuration there is nothing to attempt, so the application is
    # left exactly as it was: not "failed" and not recorded as an AI attempt.
    owner_id = application.job.owner_id
    started = time.monotonic()
    try:
        cfg = ai_provider_service.resolve_for_user(db, owner_id)
    except ai_provider_service.AIConfigurationRequiredError:
        raise
    except AIServiceError as exc:
        # A saved key that cannot be used: a real, retryable failure.
        _mark_failed(db, application, exc.message)
        _record_outcome(db, application, owner_id, {}, started, error=exc)
        raise

    job_requirements, form_answers, resume_text, resume_reason = (
        collect_analysis_inputs(application)
    )

    application.analysis_status = AnalysisStatus.ANALYZING
    application.analysis_started_at = _utcnow()
    application.analysis_error = None
    db.commit()
    db.refresh(application)

    logger.info(
        "Application analysis started: application_id=%s job_id=%s resume_text_available=%s",
        application.id,
        application.job_id,
        bool(resume_text.strip()),
    )

    started = time.monotonic()
    try:
        analysis = await analyze_application(
            job_requirements=job_requirements,
            form_answers=form_answers,
            resume_text=resume_text,
            cfg=cfg,
        )
    except AIServiceError as exc:
        safe = ai_provider_service.safe_error_for(cfg, exc)
        _mark_failed(db, application, safe.message)
        _record_outcome(db, application, owner_id, cfg, started, error=exc)
        if safe is exc:
            raise
        raise safe from None
    except Exception as exc:
        logger.exception(
            "Unexpected error while analysing application: application_id=%s", application.id
        )
        _mark_failed(db, application, UNEXPECTED_FAILURE_MESSAGE)
        _record_outcome(db, application, owner_id, cfg, started, error=exc)
        raise

    if resume_reason:
        analysis = analysis.model_copy(update={"resume_text_available": False})

    analysis = analysis.model_copy(update={"analyzed_at": _utcnow()})
    application.ai_score = analysis.match_percentage
    application.ai_analysis_details = analysis.model_dump(mode="json")
    application.analysis_status = AnalysisStatus.COMPLETED
    application.analysis_error = None
    application.analysis_started_at = None
    # Deliberately NOT touching application_status, hiring_status or
    # interview_status: the AI assists HR, it never decides for them.
    db.commit()
    db.refresh(application)
    _record_outcome(db, application, owner_id, cfg, started, score=application.ai_score)

    logger.info(
        "Application analysis completed: application_id=%s match=%s model=%s",
        application.id,
        analysis.match_percentage,
        analysis.model,
    )
    return application


def stored_analysis(application: Application) -> ApplicationAnalysis | None:
    """Return the analysis stored in PostgreSQL, or ``None``.

    Reads only — this is what ``GET`` endpoints use, so no request can trigger a
    new provider call. Unreadable legacy payloads degrade to ``None``.
    """
    details = application.ai_analysis_details
    if not isinstance(details, dict) or not details:
        return None
    try:
        return ApplicationAnalysis.model_validate(details)
    except ValidationError:
        logger.warning(
            "Stored analysis for application_id=%s could not be read", application.id
        )
        return None


# ---------------------------------------------------------------------------
# Application -> Candidate
# ---------------------------------------------------------------------------


def convert_to_candidate(db: Session, application: Application) -> Application:
    """Move an application into the candidate (hiring/interview) pipeline.

    Idempotent and concurrency-safe: the row is updated only while
    ``candidate_at`` is still NULL, and an application can never produce a
    second candidate because the candidate *is* that row. The job's
    ``leads_count`` is not touched — moving an application onwards is not a new
    application.
    """
    if application.candidate_at is not None:
        logger.info(
            "Application is already in the candidate pipeline: application_id=%s",
            application.id,
        )
        return application

    result = db.execute(
        update(Application)
        .where(Application.id == application.id, Application.candidate_at.is_(None))
        .values(candidate_at=_utcnow())
        .execution_options(synchronize_session=False)
    )
    db.commit()
    db.refresh(application)

    if result.rowcount:
        logger.info(
            "Application moved to the candidate pipeline: application_id=%s job_id=%s",
            application.id,
            application.job_id,
        )
    else:
        logger.info(
            "Concurrent candidate conversion ignored (already converted): application_id=%s",
            application.id,
        )
    return application


# ---------------------------------------------------------------------------
# Background analysis (public submissions)
# ---------------------------------------------------------------------------


async def run_analysis_in_background(application_id: int) -> None:
    """Analyse a freshly submitted application in its own database session.

    Called after a public submission returns. The applicant's request must not
    fail because the AI provider is unavailable: failures are logged and stored
    on the application (``analysis_status="failed"``) so HR can retry.
    """
    db = SessionLocal()
    try:
        application = db.get(Application, application_id)
        if application is None:
            logger.warning(
                "Background analysis skipped: application_id=%s no longer exists",
                application_id,
            )
            return
        await run_analysis(db, application)
    except AIServiceError as exc:
        logger.warning(
            "Background application analysis failed: application_id=%s reason=%s",
            application_id,
            exc.message,
        )
    except Exception:
        logger.exception(
            "Unexpected background analysis error: application_id=%s", application_id
        )
    finally:
        db.close()