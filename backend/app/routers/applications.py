"""Application/candidate API endpoints (the Applications menu's backend).

Every endpoint here works on ``applications`` rows; a "candidate" is an
application HR moved into the hiring pipeline (``candidate_at`` set).

Endpoints
---------
GET    /api/applications               — list applications (owned by caller)
POST   /api/applications               — create an application manually
GET    /api/applications/{id}          — get full application detail
PATCH  /api/applications/{id}          — update HR-owned fields
DELETE /api/applications/{id}          — delete application
POST   /api/applications/{id}/analyze  — run AI analysis (reads resume from disk)
GET    /api/applications/{id}/analysis — read stored AI analysis (never calls AI)
POST   /api/applications/{id}/convert-to-candidate — move to candidate pipeline
GET    /api/applications/{id}/resume   — view (inline) or download the stored CV
"""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.crud import batch as batch_crud
from app.crud import job as job_crud
from app.crud import application as application_crud
from app.dependencies.audit import get_audit_context
from app.dependencies.auth import get_current_user
from app.models.job import Job
from app.models.user import User
from app.models.application import AnalysisStatus, HiringStatus, InterviewStatus, Application
from app.schemas.application_analysis import ApplicationAnalysisResponse
from app.schemas.application import (
    AutoAnalyzeAvailableResponse,
    AutoAnalyzeProgressResponse,
    AutoAnalyzeStartRequest,
    AutoAnalyzeStartResponse,
    ApplicationCreate,
    ApplicationDetailResponse,
    ApplicationItemResponse,
    ApplicationUpdate,
)
from app.services import application_analysis as analysis_service
from app.services import audit
from app.services.audit import AuditAction, AuditContext, AuditResource
from app.services.ai import batch as auto_analyze_service
from app.services import resume_file as resume_file_service

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Ownership helpers
# ---------------------------------------------------------------------------


def _get_owned_job(db: Session, job_id: int, current_user: User) -> Job:
    """Return the job if it belongs to the current user, else raise 404."""
    job = job_crud.get_job(db, job_id)
    if job is None or job.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


def _get_owned_application(db: Session, application_id: int, current_user: User) -> Application:
    """Return the application if its job belongs to the current user, else raise 404."""
    application = application_crud.get_application(db, application_id)
    if application is None or application.job.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Application not found"
        )
    return application


# ---------------------------------------------------------------------------
# Build the ApplicationDetailResponse (reads stored analysis, never calls AI)
# ---------------------------------------------------------------------------


def _build_detail_response(application: Application, base_url: str = "") -> ApplicationDetailResponse:
    """Compose the full detail response for one application.

    Reads the stored AI analysis from PostgreSQL (no provider call), the
    submitted form answers, a browser-usable resume URL and the candidate's
    interviews.
    """
    from app.schemas.application import ApplicantAnswer, ApplicationInterviewSummary

    # Stored analysis (None when not yet analysed or data is unreadable).
    analysis = analysis_service.stored_analysis(application)

    # Submitted form answers from the public application form.
    response = application.application_response
    raw_answers = (response.responses if response is not None else None) or []
    answers: list[ApplicantAnswer] = []
    for ans in raw_answers:
        if not isinstance(ans, dict):
            continue
        answers.append(
            ApplicantAnswer(
                field_id=str(ans.get("field_id") or ans.get("id") or ""),
                key=str(ans.get("key") or ""),
                label=str(ans.get("label") or ""),
                type=str(ans.get("type") or ""),
                value=ans.get("value"),
            )
        )

    # The CV is only served through the authenticated endpoint below; this is
    # its API path (relative to the API base), never a filesystem location.
    resume_url = f"/applications/{application.id}/resume" if application.resume_path else None

    # Interview summaries (lightweight, avoids loading all interview details).
    interviews: list[ApplicationInterviewSummary] = [
        ApplicationInterviewSummary(
            id=interview.id,
            interviewer=interview.interviewer,
            scheduled_at=interview.scheduled_at,
            status=interview.status,
            notes=interview.notes,
        )
        for interview in (application.interviews or [])
    ]

    return ApplicationDetailResponse(
        id=application.id,
        job_id=application.job_id,
        name=application.name,
        email=application.email,
        resume_path=application.resume_path,
        ai_score=application.ai_score,
        application_status=application.application_status,
        analysis_status=application.analysis_status,
        analysis_error=application.analysis_error,
        analysis_started_at=application.analysis_started_at,
        hiring_status=application.hiring_status,
        interview_status=application.interview_status,
        is_candidate=application.is_candidate,
        candidate_at=application.candidate_at,
        created_at=application.created_at,
        submitted_at=application.submitted_at,
        company_name=application.job.company_name,
        position=application.job.position,
        resume_url=resume_url,
        responses=answers,
        analysis=analysis,
        interviews=interviews,
    )


# ---------------------------------------------------------------------------
# List / create
# ---------------------------------------------------------------------------


@router.get("", response_model=list[ApplicationItemResponse])
def list_applications(
    job_id: int | None = Query(None, description="Filter by job (must be owned by the caller)"),
    application_status: str | None = Query(None, description="Filter by application status"),
    hiring_status: HiringStatus | None = Query(None, description="Filter by hiring status"),
    interview_status: InterviewStatus | None = Query(
        None, description="Filter by interview status"
    ),
    candidate_only: bool = Query(False, description="Only return applications that are candidates"),
    search: str | None = Query(None, description="Free-text search on name/email"),
    sort: str = Query("newest", description="Sort order: newest, oldest, match"),
    skip: int = Query(0, ge=0, description="Number of applications to skip"),
    limit: int = Query(50, ge=1, le=200, description="Max applications to return"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Application]:
    """Return the current user's applications.

    Scoped to jobs owned by the caller. With no ``job_id`` this lists
    applications across all of the caller's jobs; otherwise restricted to that
    job. Supports filters for ``application_status``, ``hiring_status``,
    ``interview_status``, ``candidate_only``, free-text ``search`` and
    ``skip``/``limit`` pagination.
    """
    from app.models.application import ApplicationStatus

    if job_id is not None:
        _get_owned_job(db, job_id, current_user)

    app_status: ApplicationStatus | None = None
    if application_status:
        try:
            app_status = ApplicationStatus(application_status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid application_status: {application_status}",
            )

    return application_crud.list_applications(
        db,
        current_user.id,
        job_id=job_id,
        application_status=app_status,
        hiring_status=hiring_status,
        interview_status=interview_status,
        candidate_only=candidate_only,
        search=search,
        sort=sort,
        skip=skip,
        limit=limit,
    )


@router.post("", response_model=ApplicationItemResponse, status_code=status.HTTP_201_CREATED)
def create_application(
    job_id: int = Query(..., description="Job the application is applying for"),
    payload: ApplicationCreate = ...,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    audit_ctx: AuditContext = Depends(get_audit_context),
) -> Application:
    """Record a new application by hand and bump the job's lead count."""
    from app.services import job as job_service

    job = _get_owned_job(db, job_id, current_user)
    application = application_crud.create_application(db, job.id, payload)
    job_service.increment_leads_count(db, job.id)
    audit.record(
        db,
        AuditAction.CREATE_APPLICATION,
        resource_type=AuditResource.APPLICATION,
        resource_id=application.id,
        actor=current_user,
        details={"job_id": job.id},
        context=audit_ctx,
    )
    return application


# ---------------------------------------------------------------------------
# Get detail / update / delete
# ---------------------------------------------------------------------------


@router.get("/{application_id}", response_model=ApplicationDetailResponse)
def get_application(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApplicationDetailResponse:
    """Return a single application/candidate with full detail.

    Never triggers AI — reads only what is already stored in PostgreSQL.
    """
    application = _get_owned_application(db, application_id, current_user)
    return _build_detail_response(application)


@router.patch("/{application_id}", response_model=ApplicationDetailResponse)
def update_application(
    application_id: int,
    payload: ApplicationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    audit_ctx: AuditContext = Depends(get_audit_context),
) -> ApplicationDetailResponse:
    """Update HR-owned fields on an application/candidate."""
    application = _get_owned_application(db, application_id, current_user)
    application = application_crud.update_application(db, application, payload)
    # Statuses are enum values (safe to log); other fields only by name.
    changes = payload.model_dump(exclude_unset=True)
    audit.record(
        db,
        AuditAction.UPDATE_APPLICATION,
        resource_type=AuditResource.APPLICATION,
        resource_id=application.id,
        actor=current_user,
        details={
            "fields": sorted(changes),
            **{
                key: changes[key]
                for key in ("application_status", "hiring_status", "interview_status")
                if key in changes
            },
        },
        context=audit_ctx,
    )
    return _build_detail_response(application)


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_application(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    audit_ctx: AuditContext = Depends(get_audit_context),
) -> None:
    """Delete an application/candidate owned by the current user."""
    application = _get_owned_application(db, application_id, current_user)
    job_id = application.job_id
    application_crud.delete_application(db, application.id)
    audit.record(
        db,
        AuditAction.DELETE_APPLICATION,
        resource_type=AuditResource.APPLICATION,
        resource_id=application_id,
        actor=current_user,
        details={"job_id": job_id},
        context=audit_ctx,
    )
    return None


# ---------------------------------------------------------------------------
# AI analysis
# ---------------------------------------------------------------------------


@router.post("/{application_id}/analyze", response_model=ApplicationDetailResponse)
async def analyze_application(
    application_id: int,
    force: bool = Query(False, description="Re-run even if a completed analysis exists"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApplicationDetailResponse:
    """Run AI analysis on a submitted application.

    Uses the job requirements + submitted form answers + resume text extracted
    from the file stored on disk. Calling this when a completed analysis
    already exists is a no-op unless ``?force=true`` is passed.

    The AI provider is **never** called by ``GET`` requests — only this explicit
    trigger and the background task run on public submissions do that.

    AI never writes ``application_status``, ``hiring_status`` or
    ``interview_status`` — those remain under HR control.
    """
    from app.services.ai.job_analyzer import AIServiceError

    application = _get_owned_application(db, application_id, current_user)

    try:
        application = await analysis_service.run_analysis(db, application, force=force)
    except analysis_service.AnalysisInProgressError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=exc.message
        ) from exc
    except AIServiceError as exc:
        # The failure has already been persisted on the application — return the
        # updated application so the UI can show the retryable failed state.
        logger.warning(
            "AI analysis failed for application_id=%s: %s", application_id, exc.message
        )
        db.refresh(application)
        return _build_detail_response(application)

    return _build_detail_response(application)


@router.get("/{application_id}/analysis", response_model=ApplicationAnalysisResponse)
def get_application_analysis(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApplicationAnalysisResponse:
    """Return the stored AI analysis for an application.

    This endpoint reads from PostgreSQL only — it never calls the AI provider.
    Use ``POST /{id}/analyze`` to run or re-run the analysis.
    """
    application = _get_owned_application(db, application_id, current_user)
    analysis = analysis_service.stored_analysis(application)
    return ApplicationAnalysisResponse(
        application_id=application.id,
        analysis_status=application.analysis_status,
        analysis_error=application.analysis_error,
        analysis_started_at=application.analysis_started_at,
        ai_score=application.ai_score,
        analysis=analysis,
    )


# ---------------------------------------------------------------------------
# CV view / download
# ---------------------------------------------------------------------------


@router.get("/{application_id}/resume", response_class=FileResponse)
def get_application_resume(
    application_id: int,
    download: bool = Query(False, description="Send as an attachment instead of inline"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    """Stream the application's CV to its owner.

    Inline by default (PDFs open in the browser); ``?download=true`` sends it
    as an attachment named after the candidate. Another user's application
    returns the same 404 as a missing one.
    """
    application = _get_owned_application(db, application_id, current_user)
    try:
        resume = resume_file_service.get_resume_file(application)
    except resume_file_service.ResumeUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc

    return FileResponse(
        resume.path,
        media_type=resume.media_type,
        filename=resume.filename,
        content_disposition_type="attachment" if download else "inline",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


# ---------------------------------------------------------------------------
# Convert to candidate
# ---------------------------------------------------------------------------


@router.post(
    "/{application_id}/convert-to-candidate",
    response_model=ApplicationDetailResponse,
    status_code=status.HTTP_200_OK,
)
def convert_to_candidate(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    audit_ctx: AuditContext = Depends(get_audit_context),
) -> ApplicationDetailResponse:
    """Move an application into the candidate (hiring/interview) pipeline.

    Idempotent: calling this again on an application that is already a
    candidate is safe and returns the existing candidate record. An application
    can never produce more than one candidate because the candidate *is* that
    application row.

    AI analysis is not required before converting — HR may move an application
    to the candidate pipeline at any point.
    """
    application = _get_owned_application(db, application_id, current_user)
    already_candidate = application.candidate_at is not None
    application = analysis_service.convert_to_candidate(db, application)
    if not already_candidate:
        audit.record(
            db,
            AuditAction.CONVERT_TO_CANDIDATE,
            resource_type=AuditResource.APPLICATION,
            resource_id=application.id,
            actor=current_user,
            details={"job_id": application.job_id},
            context=audit_ctx,
        )
    return _build_detail_response(application)


# ---------------------------------------------------------------------------
# Auto-analyze batch endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/auto-analyze/available",
    response_model=AutoAnalyzeAvailableResponse,
    status_code=status.HTTP_200_OK,
)
def get_auto_analyze_available(
    job_id: int | None = Query(default=None, description="Optional job filter"),
    company: str | None = Query(default=None, max_length=255, description="Company filter"),
    position: str | None = Query(default=None, max_length=255, description="Position filter"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AutoAnalyzeAvailableResponse:
    """Count applications Auto Analyze would pick, plus the filter choices.

    Eligible = owned by the caller, ``application_status=new`` and never
    analysed. Empty/omitted filters mean "All". ``options`` lists every
    company/position pair that has eligible applications.
    """
    count = auto_analyze_service.get_available_new_count(
        db,
        current_user.id,
        job_id=job_id,
        company=(company or "").strip() or None,
        position=(position or "").strip() or None,
    )
    options = auto_analyze_service.get_filter_options(db, current_user.id)
    return AutoAnalyzeAvailableResponse(count=count, options=options)


@router.post(
    "/auto-analyze",
    response_model=AutoAnalyzeStartResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_auto_analyze(
    request: AutoAnalyzeStartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    audit_ctx: AuditContext = Depends(get_audit_context),
) -> AutoAnalyzeStartResponse:
    """Start a new auto-analyze batch.

    Selects eligible applications (new, never analysed, matching the
    optional company/position/job filters) in the requested order, up to
    ``count``, creates a batch, and returns immediately. The analysis runs in the
    background - poll GET /applications/auto-analyze/{batch_id} for progress.

    Raises:
        422: If count is not in 1-1000 range or order is invalid.
        400: If no NEW applications are available.
    """
    # Validate job_id if provided
    if request.job_id is not None:
        _get_owned_job(db, request.job_id, current_user)

    available = auto_analyze_service.get_available_new_count(
        db,
        current_user.id,
        job_id=request.job_id,
        company=request.company,
        position=request.position,
    )
    try:
        batch = auto_analyze_service.create_auto_analyze_batch(
            db,
            current_user,
            count=request.count,
            order=request.order,
            job_id=request.job_id,
            company=request.company,
            position=request.position,
        )
    except auto_analyze_service.InvalidBatchSizeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.message,
        ) from exc
    except auto_analyze_service.NoAvailableApplicationsError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message,
        ) from exc
    except auto_analyze_service.AutoAnalyzeError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.message,
        ) from exc

    selected = len(batch.application_ids)
    audit.record(
        db,
        AuditAction.AI_BATCH_STARTED,
        resource_type=AuditResource.AI_ANALYSIS,
        resource_id=batch.id,
        actor=current_user,
        details={"selected": selected, "order": request.order},
        context=audit_ctx,
    )

    # Start the background analysis
    asyncio.create_task(auto_analyze_service.run_batch_analysis(batch.id))

    return AutoAnalyzeStartResponse(
        batch_id=batch.id,
        requested_count=request.count,
        selected_count=selected,
        available_count=available,
        remaining_count=max(available - selected, 0),
        status=batch.status.value,
    )


@router.get(
    "/auto-analyze/{batch_id}",
    response_model=AutoAnalyzeProgressResponse,
    status_code=status.HTTP_200_OK,
)
def get_auto_analyze_progress(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AutoAnalyzeProgressResponse:
    """Get the current progress of an auto-analyze batch.

    Returns the batch status and progress statistics.
    """
    progress = auto_analyze_service.get_batch_progress(
        db,
        batch_id,
        current_user.id,
    )
    if progress is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found",
        )
    return AutoAnalyzeProgressResponse(**progress)


@router.post(
    "/auto-analyze/{batch_id}/cancel",
    response_model=AutoAnalyzeProgressResponse,
    status_code=status.HTTP_200_OK,
)
def cancel_auto_analyze(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AutoAnalyzeProgressResponse:
    """Cancel a running or queued auto-analyze batch.

    The batch will finish processing the current application if already
    analyzing, but no new applications will be started.
    """
    batch = batch_crud.get_batch(db, batch_id, current_user.id)
    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found",
        )

    batch = batch_crud.cancel_batch(db, batch)

    return AutoAnalyzeProgressResponse(
        batch_id=batch.id,
        status=batch.status.value,
        total=batch.total,
        processed=batch.processed,
        successful=batch.successful_count,
        failed=batch.failed_count,
        skipped=batch.skipped_count,
        remaining=batch.remaining,
        current_application_id=batch.current_application_id,
        created_at=batch.created_at,
        finished_at=batch.finished_at,
    )