"""CRUD operations for interviews.

Contains only database access, scoped to the owning HR user (``hr_id``).
``hr_id=None`` is an admin session's organisation-wide scope. Business logic
belongs in the router layer.

Invariant: ``interview.hr_id`` is always the owner of the candidate's job, even
when an admin scheduled the interview (the audit log records who acted), so
the owning HR user always sees every interview of their candidates.
"""

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, contains_eager

from app.crud.query_utils import owner_filter
from app.models.interview import Interview, InterviewStatus
from app.models.job import Job
from app.models.application import Application
from app.schemas.interview import InterviewCreate, InterviewUpdate


def _owned_query(db: Session, hr_id: int | None):
    """Base query over an HR user's interviews with candidate/job eager-loaded.

    Ownership is enforced twice (belt and braces): the ``hr_id`` column on the
    interview itself *and* the owning job's ``owner_id``, so a row can never
    leak between tenants even if its FK data were inconsistent.
    """
    return (
        db.query(Interview)
        .join(Interview.candidate)
        .join(Application.job)
        .filter(owner_filter(Interview.hr_id, hr_id), owner_filter(Job.owner_id, hr_id))
        .options(contains_eager(Interview.candidate).contains_eager(Application.job))
    )


def get_interviews(
    db: Session,
    hr_id: int | None,
    *,
    status: InterviewStatus | None = None,
    search: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[Interview]:
    """Return the HR user's interviews, newest scheduled first.

    Supports an optional ``status`` filter and a free-text ``search`` that
    matches the candidate's name or the interviewer (case-insensitive).
    """
    query = _owned_query(db, hr_id)
    if status is not None:
        query = query.filter(Interview.status == status)
    if search:
        like = f"%{search.strip().lower()}%"
        query = query.filter(
            or_(
                func.lower(Application.name).like(like),
                func.lower(Interview.interviewer).like(like),
            )
        )
    return (
        query.order_by(Interview.scheduled_at.desc(), Interview.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_interview_stats(db: Session, hr_id: int | None) -> dict[str, int]:
    """Return total/upcoming/completed/cancelled counts for the HR user (``None`` = all)."""
    base = db.query(func.count(Interview.id)).filter(owner_filter(Interview.hr_id, hr_id))

    def count_by_status(value: InterviewStatus) -> int:
        return base.filter(Interview.status == value).scalar() or 0

    return {
        "total": base.scalar() or 0,
        "upcoming": count_by_status(InterviewStatus.UPCOMING),
        "completed": count_by_status(InterviewStatus.COMPLETED),
        "cancelled": count_by_status(InterviewStatus.CANCELLED),
    }


def get_interview_by_id(db: Session, interview_id: int, hr_id: int | None) -> Interview | None:
    """Return an interview if it belongs to ``hr_id`` (``None`` = any), else ``None``."""
    return (
        db.query(Interview)
        .filter(Interview.id == interview_id, owner_filter(Interview.hr_id, hr_id))
        .first()
    )


def create_interview(db: Session, obj_in: InterviewCreate, hr_id: int) -> Interview:
    """Create and return a new interview owned by the given HR user."""
    interview = Interview(hr_id=hr_id, **obj_in.model_dump())
    db.add(interview)
    db.commit()
    db.refresh(interview)
    return interview


def update_interview(
    db: Session, db_obj: Interview, obj_in: InterviewUpdate, *, hr_id: int | None = None
) -> Interview:
    """Apply the submitted updates to an interview and return the refreshed row.

    ``hr_id`` re-assigns the interview when it moves to a candidate of another
    HR user (only possible from an admin session).
    """
    for field, value in obj_in.model_dump(exclude_unset=True).items():
        setattr(db_obj, field, value)
    if hr_id is not None:
        db_obj.hr_id = hr_id
    db.commit()
    db.refresh(db_obj)
    return db_obj


def delete_interview(db: Session, db_obj: Interview) -> None:
    """Delete the given interview."""
    db.delete(db_obj)
    db.commit()