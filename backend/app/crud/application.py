"""CRUD operations for applications (a candidate is an application HR moved on).

Contains only database access. Business logic belongs in services.
"""

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, contains_eager, selectinload

from app.crud.query_utils import owner_filter
from app.models.job import Job
from app.models.application import (
    AnalysisStatus,
    ApplicationStatus,
    HiringStatus,
    InterviewStatus,
    Application,
)
from app.models.application_status_history import ApplicationStatusHistory
from app.schemas.application import ApplicationCreate, ApplicationUpdate

#: Sort orders supported by :func:`list_applications`.
_SORT_ORDERS = {
    "newest": (Application.submitted_at.desc(), Application.id.desc()),
    "oldest": (Application.submitted_at.asc(), Application.id.asc()),
    "match": (Application.ai_score.desc(), Application.submitted_at.desc()),
}


def _record_status(db: Session, application: Application) -> None:
    """Append the application's current status to its history (same commit)."""
    status = application.application_status or ApplicationStatus.NEW
    db.add(ApplicationStatusHistory(application_id=application.id, status=ApplicationStatus(status).value))


def create_application(
    db: Session,
    job_id: int,
    payload: ApplicationCreate,
    candidate_account_id: int | None = None,
) -> Application:
    """Create and return a new application for a job.

    ``candidate_account_id`` links it to the Candidate Portal account that
    submitted it while signed in.
    """
    application = Application(
        job_id=job_id, candidate_account_id=candidate_account_id, **payload.model_dump()
    )
    db.add(application)
    db.flush()
    _record_status(db, application)
    db.commit()
    db.refresh(application)
    return application


def get_application(db: Session, application_id: int) -> Application | None:
    """Return the application with the given id, or ``None`` if it does not exist."""
    return db.get(Application, application_id)


def get_applications_for_job(db: Session, job_id: int) -> list[Application]:
    """Return all applications submitted for a given job."""
    return (
        db.query(Application)
        .filter(Application.job_id == job_id)
        .order_by(Application.created_at.desc())
        .all()
    )


def list_applications(
    db: Session,
    owner_id: int | None,
    *,
    job_id: int | None = None,
    application_status: ApplicationStatus | None = None,
    analysis_status: AnalysisStatus | None = None,
    hiring_status: HiringStatus | None = None,
    interview_status: InterviewStatus | None = None,
    candidate_only: bool = False,
    search: str | None = None,
    sort: str = "newest",
    skip: int = 0,
    limit: int = 50,
) -> list[Application]:
    """Return applications across an owner's jobs.

    The Applications UI consumes this listing: it is scoped to jobs owned by
    ``owner_id`` (no data leaks between HR users; ``None`` is an admin
    session's organisation-wide scope) and supports server-side
    filtering by ``job_id``, application/analysis/hiring/interview status, a
    free-text ``search`` on the applicant's name/email, ``candidate_only`` (the
    Candidates pipeline) and pagination via ``skip``/``limit``.

    ``contains_eager`` loads each application's job in the same query so callers can
    read ``application.job.company_name``/``position`` without the N+1 problem.
    """
    query = (
        db.query(Application)
        .join(Application.job)
        .filter(owner_filter(Job.owner_id, owner_id))
        .options(contains_eager(Application.job))
    )
    if job_id is not None:
        query = query.filter(Application.job_id == job_id)
    if application_status is not None:
        query = query.filter(Application.application_status == application_status)
    if analysis_status is not None:
        query = query.filter(Application.analysis_status == analysis_status)
    if hiring_status is not None:
        query = query.filter(Application.hiring_status == hiring_status)
    if interview_status is not None:
        query = query.filter(Application.interview_status == interview_status)
    if candidate_only:
        query = query.filter(Application.candidate_at.is_not(None))
    if search and search.strip():
        like = f"%{search.strip().lower()}%"
        query = query.filter(
            or_(
                func.lower(Application.name).like(like),
                func.lower(Application.email).like(like),
            )
        )

    order_by = _SORT_ORDERS.get(sort, _SORT_ORDERS["newest"])
    return query.order_by(*order_by).offset(skip).limit(limit).all()


def get_recent_applications(db: Session, owner_id: int | None, limit: int = 5) -> list[Application]:
    """Return the most recent applications across the owner's jobs.

    ``contains_eager`` loads each application's job in the same query so that
    dashboard code can read ``application.job.company_name`` without extra
    per-application queries (avoids the N+1 problem).
    """
    return (
        db.query(Application)
        .join(Application.job)
        .filter(owner_filter(Job.owner_id, owner_id))
        .options(contains_eager(Application.job))
        .order_by(Application.created_at.desc())
        .limit(limit)
        .all()
    )


def update_application(db: Session, application: Application, payload: ApplicationUpdate) -> Application:
    """Apply the submitted updates to an application and return the refreshed instance.

    A change of ``application_status`` is also written to the status history
    (the Candidate Portal timeline reads it).
    """
    previous_status = application.application_status
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(application, field, value)
    if application.application_status != previous_status:
        _record_status(db, application)
    db.commit()
    db.refresh(application)
    return application


def delete_application(db: Session, application_id: int) -> None:
    """Delete the application with the given id, if it exists."""
    application = db.get(Application, application_id)
    if application is not None:
        db.delete(application)
        db.commit()

# ---------------------------------------------------------------------------
# Candidate Portal (always scoped to one candidate account)
# ---------------------------------------------------------------------------


def _candidate_query(db: Session, candidate_account_id: int):
    """Applications of one candidate account, with what the portal renders."""
    return (
        db.query(Application)
        .filter(Application.candidate_account_id == candidate_account_id)
        .options(
            selectinload(Application.job),
            selectinload(Application.interviews),
            selectinload(Application.status_history),
        )
    )


def list_candidate_applications(db: Session, candidate_account_id: int) -> list[Application]:
    """Every application the candidate submitted, newest first."""
    return (
        _candidate_query(db, candidate_account_id)
        .order_by(Application.submitted_at.desc(), Application.id.desc())
        .all()
    )


def get_candidate_application(
    db: Session, candidate_account_id: int, application_id: int
) -> Application | None:
    """The application if it belongs to the candidate, else ``None``."""
    return (
        _candidate_query(db, candidate_account_id)
        .filter(Application.id == application_id)
        .first()
    )
