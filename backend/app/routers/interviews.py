"""Interview API endpoints (the Interviews menu's backend).

Interviews are plain HR-entered records for the caller's own candidates. Every
endpoint is scoped to the authenticated HR user: another user's interviews (or
candidates) behave like "not found" so no tenant data leaks.

An admin session uses the same endpoints across every HR user (see
``dependencies.auth.AccessScope``). An interview always belongs to the HR user
who owns the candidate's job, also when an admin scheduled it, so that HR user
keeps seeing it; the audit log records the admin as the actor.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.crud import interview as interview_crud
from app.crud import application as application_crud
from app.dependencies.audit import get_audit_context
from app.dependencies.auth import AccessScope, get_access_scope
from app.models.interview import Interview, InterviewStatus
from app.models.application import Application
from app.schemas.interview import (
    InterviewCreate,
    InterviewResponse,
    InterviewStats,
    InterviewUpdate,
)
from app.services import audit
from app.services.audit import AuditAction, AuditContext, AuditResource

router = APIRouter()


def _get_owned_application(db: Session, application_id: int, scope: AccessScope) -> Application:
    """Return the candidate if their job is in the caller's scope, else 404."""
    application = application_crud.get_application(db, application_id)
    if application is None or not scope.can_access(application.job.owner_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found"
        )
    return application


def _get_owned_interview(db: Session, interview_id: int, scope: AccessScope) -> Interview:
    """Return the interview if it is in the caller's scope, else 404."""
    interview = interview_crud.get_interview_by_id(db, interview_id, scope.owner_id)
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
    scope: AccessScope = Depends(get_access_scope),
) -> list[InterviewResponse]:
    """Return the caller's interviews (all of them in an admin session)."""
    interviews = interview_crud.get_interviews(
        db,
        scope.owner_id,
        status=status_filter,
        search=search,
        skip=skip,
        limit=limit,
    )
    return [_to_response(interview) for interview in interviews]


@router.get("/stats", response_model=InterviewStats)
def get_stats(
    db: Session = Depends(get_db),
    scope: AccessScope = Depends(get_access_scope),
) -> InterviewStats:
    """Return interview counts by status for the metric cards."""
    return InterviewStats(**interview_crud.get_interview_stats(db, scope.owner_id))


@router.post("", response_model=InterviewResponse, status_code=status.HTTP_201_CREATED)
def create_interview(
    payload: InterviewCreate,
    db: Session = Depends(get_db),
    scope: AccessScope = Depends(get_access_scope),
    audit_ctx: AuditContext = Depends(get_audit_context),
) -> InterviewResponse:
    """Schedule a new interview for a candidate in the caller's scope."""
    candidate = _get_owned_application(db, payload.candidate_id, scope)
    interview = interview_crud.create_interview(db, payload, candidate.job.owner_id)
    audit.record(
        db,
        AuditAction.CREATE_INTERVIEW,
        resource_type=AuditResource.INTERVIEW,
        resource_id=interview.id,
        actor=scope.user,
        details={"candidate_id": interview.candidate_id},
        context=audit_ctx,
    )
    return _to_response(interview)


@router.get("/{interview_id}", response_model=InterviewResponse)
def get_interview(
    interview_id: int,
    db: Session = Depends(get_db),
    scope: AccessScope = Depends(get_access_scope),
) -> InterviewResponse:
    """Return a single interview in the caller's scope."""
    interview = _get_owned_interview(db, interview_id, scope)
    return _to_response(interview)


@router.patch("/{interview_id}", response_model=InterviewResponse)
def update_interview(
    interview_id: int,
    payload: InterviewUpdate,
    db: Session = Depends(get_db),
    scope: AccessScope = Depends(get_access_scope),
    audit_ctx: AuditContext = Depends(get_audit_context),
) -> InterviewResponse:
    """Update an interview (status, notes, meeting link, time, interviewer)."""
    interview = _get_owned_interview(db, interview_id, scope)
    new_owner_id = None
    if payload.candidate_id is not None:
        # Re-validate ownership when the interview is moved to another candidate
        # (and keep it with that candidate's HR owner).
        candidate = _get_owned_application(db, payload.candidate_id, scope)
        new_owner_id = candidate.job.owner_id
    interview = interview_crud.update_interview(db, interview, payload, hr_id=new_owner_id)
    details: dict = {"fields": audit.changed_fields(payload)}
    if payload.status is not None:
        details["status"] = payload.status
    audit.record(
        db,
        AuditAction.UPDATE_INTERVIEW,
        resource_type=AuditResource.INTERVIEW,
        resource_id=interview.id,
        actor=scope.user,
        details=details,
        context=audit_ctx,
    )
    return _to_response(interview)


@router.delete("/{interview_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_interview(
    interview_id: int,
    db: Session = Depends(get_db),
    scope: AccessScope = Depends(get_access_scope),
    audit_ctx: AuditContext = Depends(get_audit_context),
) -> None:
    """Delete an interview in the caller's scope."""
    interview = _get_owned_interview(db, interview_id, scope)
    candidate_id = interview.candidate_id
    interview_crud.delete_interview(db, interview)
    audit.record(
        db,
        AuditAction.DELETE_INTERVIEW,
        resource_type=AuditResource.INTERVIEW,
        resource_id=interview_id,
        actor=scope.user,
        details={"candidate_id": candidate_id},
        context=audit_ctx,
    )
    return None