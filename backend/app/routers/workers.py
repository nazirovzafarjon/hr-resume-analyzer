"""Worker/candidate API endpoints (the Applications menu's backend).

A ``Worker`` attached to a ``Job`` *is* an Application, so everything here
operates on the existing ``workers`` table — no separate applications table.

Endpoints
---------
GET    /api/workers               — list applications (owned by caller)
POST   /api/workers               — create a worker manually
GET    /api/workers/{id}          — get full application detail
PATCH  /api/workers/{id}          — update HR-owned fields
DELETE /api/workers/{id}          — delete worker
POST   /api/workers/{id}/analyze  — run AI analysis (reads resume from disk)
GET    /api/workers/{id}/analysis — read stored AI analysis (never calls AI)
POST   /api/workers/{id}/convert-to-candidate — move to candidate pipeline
"""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.crud import batch as batch_crud
from app.crud import job as job_crud
from app.crud import worker as worker_crud
from app.dependencies.auth import get_current_user
from app.models.job import Job
from app.models.user import User
from app.models.worker import AnalysisStatus, HiringStatus, InterviewStatus, Worker
from app.schemas.application_analysis import ApplicationAnalysisResponse
from app.schemas.worker import (
    AutoAnalyzeAvailableResponse,
    AutoAnalyzeProgressResponse,
    AutoAnalyzeStartRequest,
    AutoAnalyzeStartResponse,
    WorkerCreate,
    WorkerDetailResponse,
    WorkerResponse,
    WorkerUpdate,
)
from app.services import application_analysis as analysis_service
from app.services import auto_analyze as auto_analyze_service

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


def _get_owned_worker(db: Session, worker_id: int, current_user: User) -> Worker:
    """Return the worker if its job belongs to the current user, else raise 404."""
    worker = worker_crud.get_worker(db, worker_id)
    if worker is None or worker.job.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Worker not found"
        )
    return worker


# ---------------------------------------------------------------------------
# Build the WorkerDetailResponse (reads stored analysis, never calls AI)
# ---------------------------------------------------------------------------


def _build_detail_response(worker: Worker, base_url: str = "") -> WorkerDetailResponse:
    """Compose the full detail response for one worker.

    Reads the stored AI analysis from PostgreSQL (no provider call), the
    submitted form answers, a browser-usable resume URL and the candidate's
    interviews.
    """
    from app.schemas.worker import ApplicantAnswer, WorkerInterviewSummary

    # Stored analysis (None when not yet analysed or data is unreadable).
    analysis = analysis_service.stored_analysis(worker)

    # Submitted form answers from the public application form.
    response = worker.application_response
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

    # Browser-usable URL for the stored resume file.
    resume_url: str | None = None
    if worker.resume_path:
        if worker.resume_path.startswith("http"):
            resume_url = worker.resume_path
        else:
            # Strip any leading slash from the stored path segment.
            path_segment = worker.resume_path.lstrip("/")
            resume_url = f"{base_url}/{path_segment}" if base_url else f"/{path_segment}"

    # Interview summaries (lightweight, avoids loading all interview details).
    interviews: list[WorkerInterviewSummary] = [
        WorkerInterviewSummary(
            id=interview.id,
            interviewer=interview.interviewer,
            scheduled_at=interview.scheduled_at,
            status=interview.status,
            notes=interview.notes,
        )
        for interview in (worker.interviews or [])
    ]

    return WorkerDetailResponse(
        id=worker.id,
        job_id=worker.job_id,
        name=worker.name,
        email=worker.email,
        resume_path=worker.resume_path,
        ai_score=worker.ai_score,
        application_status=worker.application_status,
        analysis_status=worker.analysis_status,
        analysis_error=worker.analysis_error,
        analysis_started_at=worker.analysis_started_at,
        hiring_status=worker.hiring_status,
        interview_status=worker.interview_status,
        is_candidate=worker.is_candidate,
        candidate_at=worker.candidate_at,
        created_at=worker.created_at,
        submitted_at=worker.submitted_at,
        company_name=worker.job.company_name,
        position=worker.job.position,
        resume_url=resume_url,
        responses=answers,
        analysis=analysis,
        interviews=interviews,
    )


# ---------------------------------------------------------------------------
# List / create
# ---------------------------------------------------------------------------


@router.get("", response_model=list[WorkerResponse])
def list_workers(
    job_id: int | None = Query(None, description="Filter by job (must be owned by the caller)"),
    application_status: str | None = Query(None, description="Filter by application status"),
    hiring_status: HiringStatus | None = Query(None, description="Filter by hiring status"),
    interview_status: InterviewStatus | None = Query(
        None, description="Filter by interview status"
    ),
    candidate_only: bool = Query(False, description="Only return workers that are candidates"),
    search: str | None = Query(None, description="Free-text search on name/email"),
    sort: str = Query("newest", description="Sort order: newest, oldest, match"),
    skip: int = Query(0, ge=0, description="Number of applications to skip"),
    limit: int = Query(50, ge=1, le=200, description="Max applications to return"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Worker]:
    """Return the current user's applications (workers).

    Scoped to jobs owned by the caller. With no ``job_id`` this lists
    applications across all of the caller's jobs; otherwise restricted to that
    job. Supports filters for ``application_status``, ``hiring_status``,
    ``interview_status``, ``candidate_only``, free-text ``search`` and
    ``skip``/``limit`` pagination.
    """
    from app.models.worker import ApplicationStatus

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

    return worker_crud.list_workers(
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


@router.post("", response_model=WorkerResponse, status_code=status.HTTP_201_CREATED)
def create_worker(
    job_id: int = Query(..., description="Job the worker is applying for"),
    payload: WorkerCreate = ...,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Worker:
    """Record a new worker/candidate application and bump the job's lead count."""
    from app.services import job as job_service

    job = _get_owned_job(db, job_id, current_user)
    worker = worker_crud.create_worker(db, job.id, payload)
    job_service.increment_leads_count(db, job.id)
    return worker


# ---------------------------------------------------------------------------
# Get detail / update / delete
# ---------------------------------------------------------------------------


@router.get("/{worker_id}", response_model=WorkerDetailResponse)
def get_worker(
    worker_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkerDetailResponse:
    """Return a single application/candidate with full detail.

    Never triggers AI — reads only what is already stored in PostgreSQL.
    """
    worker = _get_owned_worker(db, worker_id, current_user)
    return _build_detail_response(worker)


@router.patch("/{worker_id}", response_model=WorkerDetailResponse)
def update_worker(
    worker_id: int,
    payload: WorkerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkerDetailResponse:
    """Update HR-owned fields on an application/candidate."""
    worker = _get_owned_worker(db, worker_id, current_user)
    worker = worker_crud.update_worker(db, worker, payload)
    return _build_detail_response(worker)


@router.delete("/{worker_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_worker(
    worker_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a worker/candidate owned by the current user."""
    worker = _get_owned_worker(db, worker_id, current_user)
    worker_crud.delete_worker(db, worker.id)
    return None


# ---------------------------------------------------------------------------
# AI analysis
# ---------------------------------------------------------------------------


@router.post("/{worker_id}/analyze", response_model=WorkerDetailResponse)
async def analyze_worker(
    worker_id: int,
    force: bool = Query(False, description="Re-run even if a completed analysis exists"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkerDetailResponse:
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

    worker = _get_owned_worker(db, worker_id, current_user)

    try:
        worker = await analysis_service.run_analysis(db, worker, force=force)
    except analysis_service.AnalysisInProgressError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=exc.message
        ) from exc
    except AIServiceError as exc:
        # The failure has already been persisted on the worker — return the
        # updated worker so the UI can show the retryable failed state.
        logger.warning(
            "AI analysis failed for worker_id=%s: %s", worker_id, exc.message
        )
        db.refresh(worker)
        return _build_detail_response(worker)

    return _build_detail_response(worker)


@router.get("/{worker_id}/analysis", response_model=ApplicationAnalysisResponse)
def get_worker_analysis(
    worker_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApplicationAnalysisResponse:
    """Return the stored AI analysis for an application.

    This endpoint reads from PostgreSQL only — it never calls the AI provider.
    Use ``POST /{id}/analyze`` to run or re-run the analysis.
    """
    worker = _get_owned_worker(db, worker_id, current_user)
    analysis = analysis_service.stored_analysis(worker)
    return ApplicationAnalysisResponse(
        worker_id=worker.id,
        analysis_status=worker.analysis_status,
        analysis_error=worker.analysis_error,
        analysis_started_at=worker.analysis_started_at,
        ai_score=worker.ai_score,
        analysis=analysis,
    )


# ---------------------------------------------------------------------------
# Convert to candidate
# ---------------------------------------------------------------------------


@router.post(
    "/{worker_id}/convert-to-candidate",
    response_model=WorkerDetailResponse,
    status_code=status.HTTP_200_OK,
)
def convert_to_candidate(
    worker_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkerDetailResponse:
    """Move an application into the candidate (hiring/interview) pipeline.

    Idempotent: calling this again on an application that is already a
    candidate is safe and returns the existing candidate record. An application
    can never produce more than one candidate because the candidate *is* that
    application row.

    AI analysis is not required before converting — HR may move an application
    to the candidate pipeline at any point.
    """
    worker = _get_owned_worker(db, worker_id, current_user)
    worker = analysis_service.convert_to_candidate(db, worker)
    return _build_detail_response(worker)


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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AutoAnalyzeAvailableResponse:
    """Get the count of NEW applications available for auto-analysis.

    Returns the number of applications with analysis_status=NEW that belong
    to the current user's jobs. Optionally filtered by job_id.
    """
    count = auto_analyze_service.get_available_new_count(
        db,
        current_user.id,
        job_id=job_id,
    )
    return AutoAnalyzeAvailableResponse(count=count)


@router.post(
    "/auto-analyze",
    response_model=AutoAnalyzeStartResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_auto_analyze(
    request: AutoAnalyzeStartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AutoAnalyzeStartResponse:
    """Start a new auto-analyze batch.

    Selects NEW applications according to the requested order and count,
    creates a batch, and returns immediately. The analysis runs in the
    background - poll GET /workers/auto-analyze/{batch_id} for progress.

    Raises:
        422: If count is not in 1-1000 range or order is invalid.
        400: If no NEW applications are available.
    """
    # Validate job_id if provided
    if request.job_id is not None:
        _get_owned_job(db, request.job_id, current_user)

    try:
        batch = auto_analyze_service.create_auto_analyze_batch(
            db,
            current_user,
            count=request.count,
            order=request.order,
            job_id=request.job_id,
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

    # Start the background analysis
    asyncio.create_task(auto_analyze_service.run_batch_analysis(batch.id))

    return AutoAnalyzeStartResponse(
        batch_id=batch.id,
        requested_count=request.count,
        selected_count=len(batch.worker_ids),
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
        remaining=batch.remaining,
        current_application_id=batch.current_worker_id,
        created_at=batch.created_at,
        finished_at=batch.finished_at,
    )