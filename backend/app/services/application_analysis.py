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
from app.models.worker import AnalysisStatus, Worker
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


def build_form_answers(worker: Worker) -> str:
    """Render every answer the applicant submitted as ``Label: value`` lines.

    All submitted fields are included (the public form supports HR-authored
    custom questions), never only name/email/phone. Applications recorded
    manually by HR have no stored answers, so their identity fields are used
    instead.
    """
    response = worker.application_response
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
        lines.append(f"Applicant name: {worker.name}")
        lines.append(f"Applicant email: {worker.email}")
    return "\n".join(lines)


def collect_analysis_inputs(worker: Worker) -> tuple[str, str, str, str | None]:
    """Return ``(job_requirements, form_answers, resume_text, resume_reason)``.

    ``resume_reason`` explains why no resume text is available (unsupported
    format, missing file, scanned PDF, ...) and is ``None`` when text was
    extracted.
    """
    resume = extract_resume_text(worker.resume_path or "")
    return (
        build_job_requirements(worker.job),
        build_form_answers(worker),
        resume.text,
        resume.unavailable_reason,
    )
# ---------------------------------------------------------------------------
# Run + persist
# ---------------------------------------------------------------------------


def _is_run_active(worker: Worker) -> bool:
    """True when an analysis run is currently in flight (and not stale)."""
    if worker.analysis_status != AnalysisStatus.ANALYZING:
        return False
    started = worker.analysis_started_at
    if started is None:
        return True
    if started.tzinfo is None:  # Defensive: treat naive values as UTC.
        started = started.replace(tzinfo=timezone.utc)
    return _utcnow() - started < timedelta(seconds=STALE_ANALYSIS_SECONDS)


def _mark_failed(db: Session, worker: Worker, message: str | None) -> None:
    """Persist a failed analysis attempt (the application itself is kept)."""
    worker.analysis_status = AnalysisStatus.FAILED
    worker.analysis_error = (message or UNEXPECTED_FAILURE_MESSAGE)[:500]
    worker.analysis_started_at = None
    db.commit()
    db.refresh(worker)
    logger.warning(
        "Application analysis failed: worker_id=%s reason=%s",
        worker.id,
        worker.analysis_error,
    )


def _record_outcome(
    db: Session,
    worker: Worker,
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
        job_id=worker.job_id,
        worker_id=worker.id,
        score=score,
        error=error,
    )
    audit.record(
        db,
        audit.AuditAction.AI_ANALYSIS_FAILED if error else audit.AuditAction.AI_ANALYSIS_COMPLETED,
        resource_type=audit.AuditResource.APPLICATION,
        resource_id=worker.id,
        details={"job_id": worker.job_id, "owner_id": owner_id, "score": score}
        if error is None
        else {"job_id": worker.job_id, "owner_id": owner_id, "category": ai_monitoring.categorize(error)},
    )


async def run_analysis(db: Session, worker: Worker, *, force: bool = False) -> Worker:
    """Analyse one application and store the structured result.

    The job requirements, the submitted form answers and the extracted resume
    text are sent to the configured AI provider. A provider failure is recorded
    as ``analysis_status="failed"`` with a safe message — the application and
    everything HR already has stay untouched and the run can be retried.

    Args:
        db: Active database session.
        worker: The application/candidate being analysed.
        force: When ``False`` (default) an application that already has a stored
            analysis is returned as-is, so the provider is never called
            implicitly (page loads must not trigger AI).

    Raises:
        AnalysisInProgressError: A run is already in flight for this row.
        AIServiceError: The provider (or our validation) failed.
    """
    if (
        not force
        and worker.analysis_status == AnalysisStatus.COMPLETED
        and worker.ai_analysis_details
    ):
        logger.info(
            "Application already analysed -- skipping AI call: worker_id=%s",
            worker.id,
        )
        return worker

    if _is_run_active(worker):
        raise AnalysisInProgressError()

    job_requirements, form_answers, resume_text, resume_reason = (
        collect_analysis_inputs(worker)
    )

    worker.analysis_status = AnalysisStatus.ANALYZING
    worker.analysis_started_at = _utcnow()
    worker.analysis_error = None
    db.commit()
    db.refresh(worker)

    logger.info(
        "Application analysis started: worker_id=%s job_id=%s resume_text_available=%s",
        worker.id,
        worker.job_id,
        bool(resume_text.strip()),
    )

    cfg: dict = {}
    owner_id = worker.job.owner_id
    started = time.monotonic()
    try:
        # The job owner's own provider when configured, else the platform's.
        cfg = ai_provider_service.resolve_for_user(db, owner_id)
        analysis = await analyze_application(
            job_requirements=job_requirements,
            form_answers=form_answers,
            resume_text=resume_text,
            cfg=cfg,
        )
    except AIServiceError as exc:
        safe = ai_provider_service.safe_error_for(cfg, exc)
        _mark_failed(db, worker, safe.message)
        _record_outcome(db, worker, owner_id, cfg, started, error=exc)
        if safe is exc:
            raise
        raise safe from None
    except Exception as exc:
        logger.exception(
            "Unexpected error while analysing application: worker_id=%s", worker.id
        )
        _mark_failed(db, worker, UNEXPECTED_FAILURE_MESSAGE)
        _record_outcome(db, worker, owner_id, cfg, started, error=exc)
        raise

    if resume_reason:
        analysis = analysis.model_copy(update={"resume_text_available": False})

    analysis = analysis.model_copy(update={"analyzed_at": _utcnow()})
    worker.ai_score = analysis.match_percentage
    worker.ai_analysis_details = analysis.model_dump(mode="json")
    worker.analysis_status = AnalysisStatus.COMPLETED
    worker.analysis_error = None
    worker.analysis_started_at = None
    # Deliberately NOT touching application_status, hiring_status or
    # interview_status: the AI assists HR, it never decides for them.
    db.commit()
    db.refresh(worker)
    _record_outcome(db, worker, owner_id, cfg, started, score=worker.ai_score)

    logger.info(
        "Application analysis completed: worker_id=%s match=%s model=%s",
        worker.id,
        analysis.match_percentage,
        analysis.model,
    )
    return worker


def stored_analysis(worker: Worker) -> ApplicationAnalysis | None:
    """Return the analysis stored in PostgreSQL, or ``None``.

    Reads only — this is what ``GET`` endpoints use, so no request can trigger a
    new provider call. Unreadable legacy payloads degrade to ``None``.
    """
    details = worker.ai_analysis_details
    if not isinstance(details, dict) or not details:
        return None
    try:
        return ApplicationAnalysis.model_validate(details)
    except ValidationError:
        logger.warning(
            "Stored analysis for worker_id=%s could not be read", worker.id
        )
        return None


# ---------------------------------------------------------------------------
# Application -> Candidate
# ---------------------------------------------------------------------------


def convert_to_candidate(db: Session, worker: Worker) -> Worker:
    """Move an application into the candidate (hiring/interview) pipeline.

    Idempotent and concurrency-safe: the row is updated only while
    ``candidate_at`` is still NULL, and an application can never produce a
    second candidate because the candidate *is* that row. The job's
    ``leads_count`` is not touched — moving an application onwards is not a new
    application.
    """
    if worker.candidate_at is not None:
        logger.info(
            "Application is already in the candidate pipeline: worker_id=%s",
            worker.id,
        )
        return worker

    result = db.execute(
        update(Worker)
        .where(Worker.id == worker.id, Worker.candidate_at.is_(None))
        .values(candidate_at=_utcnow())
        .execution_options(synchronize_session=False)
    )
    db.commit()
    db.refresh(worker)

    if result.rowcount:
        logger.info(
            "Application moved to the candidate pipeline: worker_id=%s job_id=%s",
            worker.id,
            worker.job_id,
        )
    else:
        logger.info(
            "Concurrent candidate conversion ignored (already converted): worker_id=%s",
            worker.id,
        )
    return worker


# ---------------------------------------------------------------------------
# Background analysis (public submissions)
# ---------------------------------------------------------------------------


async def run_analysis_in_background(worker_id: int) -> None:
    """Analyse a freshly submitted application in its own database session.

    Called after a public submission returns. The applicant's request must not
    fail because the AI provider is unavailable: failures are logged and stored
    on the application (``analysis_status="failed"``) so HR can retry.
    """
    db = SessionLocal()
    try:
        worker = db.get(Worker, worker_id)
        if worker is None:
            logger.warning(
                "Background analysis skipped: worker_id=%s no longer exists",
                worker_id,
            )
            return
        await run_analysis(db, worker)
    except AIServiceError as exc:
        logger.warning(
            "Background application analysis failed: worker_id=%s reason=%s",
            worker_id,
            exc.message,
        )
    except Exception:
        logger.exception(
            "Unexpected background analysis error: worker_id=%s", worker_id
        )
    finally:
        db.close()