"""Interview API endpoints (the Interviews menu's backend).

Interviews are plain HR-entered records for the caller's own candidates. Every
endpoint is scoped to the authenticated HR user: another user's interviews (or
candidates) behave like "not found" so no tenant data leaks.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.crud import interview as interview_crud
from app.crud import worker as worker_crud
from app.dependencies.audit import get_audit_context
from app.dependencies.auth import get_current_user
from app.models.interview import Interview, InterviewStatus
from app.models.user import User
from app.models.worker import Worker
from app.schemas.interview import (
    InterviewCreate,
    InterviewResponse,
    InterviewStats,
    InterviewUpdate,
)
from app.services import audit
from app.services.audit import AuditAction, AuditContext, AuditResource

router = APIRouter()


def _get_owned_worker(db: Session, worker_id: int, current_user: User) -> Worker:
    """Return the candidate if their job belongs to the current user, else 404."""
    worker = worker_crud.get_worker(db, worker_id)
    if worker is None or worker.job.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found"
        )
    return worker


def _get_owned_interview(db: Session, interview_id: int, current_user: User) -> Interview:
    """Return the interview if it belongs to the current user, else 404."""
    interview = interview_crud.get_interview_by_id(db, interview_id, current_user.id)
    if interview is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found"
        )
    return interview


def _to_response(interview: Interview) -> InterviewResponse:
    """Build the API payload, enriching the row with candidate/job context."""
    candidate = interview.candidate
    job = candidate.job
    return InterviewResponse(
        id=interview.id,
        candidate_id=interview.candidate_id,
        hr_id=interview.hr_id,
        interviewer=interview.interviewer,
        scheduled_at=interview.scheduled_at,
        duration_minutes=interview.duration_minutes,
        status=interview.status,
        meeting_link=interview.meeting_link,
        notes=interview.notes,
        job_id=job.id,
        candidate_name=candidate.name,
        job_title=job.position,
        company_name=job.company_name,
        created_at=interview.created_at,
        updated_at=interview.updated_at,
    )


@router.get("", response_model=list[InterviewResponse])
def list_interviews(
    status_filter: InterviewStatus | None = Query(
        None, alias="status", description="Filter by status (upcoming/completed/cancelled)"
    ),
    search: str | None = Query(
        None, max_length=100, description="Search by candidate name or interviewer"
    ),
    skip: int = Query(0, ge=0, description="Number of interviews to skip"),
    limit: int = Query(100, ge=1, le=500, description="Max interviews to return"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[InterviewResponse]:
    """Return the current user's interviews with optional filters."""
    interviews = interview_crud.get_interviews(
        db,
        current_user.id,
        status=status_filter,
        search=search,
        skip=skip,
        limit=limit,
    )
    return [_to_response(interview) for interview in interviews]


@router.get("/stats", response_model=InterviewStats)
def get_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InterviewStats:
    """Return interview counts by status for the metric cards."""
    return InterviewStats(**interview_crud.get_interview_stats(db, current_user.id))


@router.post("", response_model=InterviewResponse, status_code=status.HTTP_201_CREATED)
def create_interview(
    payload: InterviewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    audit_ctx: AuditContext = Depends(get_audit_context),
) -> InterviewResponse:
    """Schedule a new interview for one of the current user's candidates."""
    _get_owned_worker(db, payload.candidate_id, current_user)
    interview = interview_crud.create_interview(db, payload, current_user.id)
    audit.record(
        db,
        AuditAction.CREATE_INTERVIEW,
        resource_type=AuditResource.INTERVIEW,
        resource_id=interview.id,
        actor=current_user,
        details={"candidate_id": interview.candidate_id},
        context=audit_ctx,
    )
    return _to_response(interview)


@router.get("/{interview_id}", response_model=InterviewResponse)
def get_interview(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InterviewResponse:
    """Return a single interview owned by the current user."""
    interview = _get_owned_interview(db, interview_id, current_user)
    return _to_response(interview)


@router.patch("/{interview_id}", response_model=InterviewResponse)
def update_interview(
    interview_id: int,
    payload: InterviewUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    audit_ctx: AuditContext = Depends(get_audit_context),
) -> InterviewResponse:
    """Update an interview (status, notes, meeting link, time, interviewer)."""
    interview = _get_owned_interview(db, interview_id, current_user)
    if payload.candidate_id is not None:
        # Re-validate ownership when the interview is moved to another candidate.
        _get_owned_worker(db, payload.candidate_id, current_user)
    interview = interview_crud.update_interview(db, interview, payload)
    details: dict = {"fields": audit.changed_fields(payload)}
    if payload.status is not None:
        details["status"] = payload.status
    audit.record(
        db,
        AuditAction.UPDATE_INTERVIEW,
        resource_type=AuditResource.INTERVIEW,
        resource_id=interview.id,
        actor=current_user,
        details=details,
        context=audit_ctx,
    )
    return _to_response(interview)


@router.delete("/{interview_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_interview(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    audit_ctx: AuditContext = Depends(get_audit_context),
) -> None:
    """Delete an interview owned by the current user."""
    interview = _get_owned_interview(db, interview_id, current_user)
    candidate_id = interview.candidate_id
    interview_crud.delete_interview(db, interview)
    audit.record(
        db,
        AuditAction.DELETE_INTERVIEW,
        resource_type=AuditResource.INTERVIEW,
        resource_id=interview_id,
        actor=current_user,
        details={"candidate_id": candidate_id},
        context=audit_ctx,
    )
    return None