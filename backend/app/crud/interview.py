"""CRUD operations for interviews.

Contains only database access, scoped to the owning HR user (``hr_id``).
Business logic belongs in the router layer.
"""

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, contains_eager

from app.models.interview import Interview, InterviewStatus
from app.models.job import Job
from app.models.application import Application
from app.schemas.interview import InterviewCreate, InterviewUpdate


def _owned_query(db: Session, hr_id: int):
    """Base query over an HR user's interviews with candidate/job eager-loaded.

    Ownership is enforced twice (belt and braces): the ``hr_id`` column on the
    interview itself *and* the owning job's ``owner_id``, so a row can never
    leak between tenants even if its FK data were inconsistent.
    """
    return (
        db.query(Interview)
        .join(Interview.candidate)
        .join(Application.job)
        .filter(Interview.hr_id == hr_id, Job.owner_id == hr_id)
        .options(contains_eager(Interview.candidate).contains_eager(Application.job))
    )


def get_interviews(
    db: Session,
    hr_id: int,
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


def get_interview_stats(db: Session, hr_id: int) -> dict[str, int]:
    """Return total/upcoming/completed/cancelled counts for the HR user."""
    base = db.query(func.count(Interview.id)).filter(Interview.hr_id == hr_id)

    def count_by_status(value: InterviewStatus) -> int:
        return base.filter(Interview.status == value).scalar() or 0

    return {
        "total": base.scalar() or 0,
        "upcoming": count_by_status(InterviewStatus.UPCOMING),
        "completed": count_by_status(InterviewStatus.COMPLETED),
        "cancelled": count_by_status(InterviewStatus.CANCELLED),
    }


def get_interview_by_id(db: Session, interview_id: int, hr_id: int) -> Interview | None:
    """Return an interview if it belongs to ``hr_id``, else ``None``."""
    return (
        db.query(Interview)
        .filter(Interview.id == interview_id, Interview.hr_id == hr_id)
        .first()
    )


def create_interview(db: Session, obj_in: InterviewCreate, hr_id: int) -> Interview:
    """Create and return a new interview owned by the given HR user."""
    interview = Interview(hr_id=hr_id, **obj_in.model_dump())
    db.add(interview)
    db.commit()
    db.refresh(interview)
    return interview


def update_interview(db: Session, db_obj: Interview, obj_in: InterviewUpdate) -> Interview:
    """Apply the submitted updates to an interview and return the refreshed row."""
    for field, value in obj_in.model_dump(exclude_unset=True).items():
        setattr(db_obj, field, value)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def delete_interview(db: Session, db_obj: Interview) -> None:
    """Delete the given interview."""
    db.delete(db_obj)
    db.commit()