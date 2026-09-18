"""CRUD operations for workers/candidates (applications).

Contains only database access. Business logic belongs in services.
"""

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, contains_eager

from app.models.job import Job
from app.models.worker import (
    AnalysisStatus,
    ApplicationStatus,
    HiringStatus,
    InterviewStatus,
    Worker,
)
from app.schemas.worker import WorkerCreate, WorkerUpdate

#: Sort orders supported by :func:`list_workers`.
_SORT_ORDERS = {
    "newest": (Worker.submitted_at.desc(), Worker.id.desc()),
    "oldest": (Worker.submitted_at.asc(), Worker.id.asc()),
    "match": (Worker.ai_score.desc(), Worker.submitted_at.desc()),
}


def create_worker(db: Session, job_id: int, payload: WorkerCreate) -> Worker:
    """Create and return a new worker/candidate application for a job."""
    worker = Worker(job_id=job_id, **payload.model_dump())
    db.add(worker)
    db.commit()
    db.refresh(worker)
    return worker


def get_worker(db: Session, worker_id: int) -> Worker | None:
    """Return the worker with the given id, or ``None`` if it does not exist."""
    return db.get(Worker, worker_id)


def get_workers_for_job(db: Session, job_id: int) -> list[Worker]:
    """Return all workers/candidates that applied for a given job."""
    return (
        db.query(Worker)
        .filter(Worker.job_id == job_id)
        .order_by(Worker.created_at.desc())
        .all()
    )


def list_workers(
    db: Session,
    owner_id: int,
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
) -> list[Worker]:
    """Return applications (workers) across an owner's jobs.

    The Applications UI consumes this listing: it is scoped to jobs owned by
    ``owner_id`` (no data leaks between HR users) and supports server-side
    filtering by ``job_id``, application/analysis/hiring/interview status, a
    free-text ``search`` on the applicant's name/email, ``candidate_only`` (the
    Candidates pipeline) and pagination via ``skip``/``limit``.

    ``contains_eager`` loads each worker's job in the same query so callers can
    read ``worker.job.company_name``/``position`` without the N+1 problem.
    """
    query = (
        db.query(Worker)
        .join(Worker.job)
        .filter(Job.owner_id == owner_id)
        .options(contains_eager(Worker.job))
    )
    if job_id is not None:
        query = query.filter(Worker.job_id == job_id)
    if application_status is not None:
        query = query.filter(Worker.application_status == application_status)
    if analysis_status is not None:
        query = query.filter(Worker.analysis_status == analysis_status)
    if hiring_status is not None:
        query = query.filter(Worker.hiring_status == hiring_status)
    if interview_status is not None:
        query = query.filter(Worker.interview_status == interview_status)
    if candidate_only:
        query = query.filter(Worker.candidate_at.is_not(None))
    if search and search.strip():
        like = f"%{search.strip().lower()}%"
        query = query.filter(
            or_(
                func.lower(Worker.name).like(like),
                func.lower(Worker.email).like(like),
            )
        )

    order_by = _SORT_ORDERS.get(sort, _SORT_ORDERS["newest"])
    return query.order_by(*order_by).offset(skip).limit(limit).all()


def get_recent_workers(db: Session, owner_id: int, limit: int = 5) -> list[Worker]:
    """Return the most recent workers/candidates across the owner's jobs.

    ``contains_eager`` loads each worker's job in the same query so that
    dashboard code can read ``worker.job.company_name`` without extra
    per-worker queries (avoids the N+1 problem).
    """
    return (
        db.query(Worker)
        .join(Worker.job)
        .filter(Job.owner_id == owner_id)
        .options(contains_eager(Worker.job))
        .order_by(Worker.created_at.desc())
        .limit(limit)
        .all()
    )


def update_worker(db: Session, worker: Worker, payload: WorkerUpdate) -> Worker:
    """Apply the submitted updates to a worker and return the refreshed instance."""
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(worker, field, value)
    db.commit()
    db.refresh(worker)
    return worker


def delete_worker(db: Session, worker_id: int) -> None:
    """Delete the worker with the given id, if it exists."""
    worker = db.get(Worker, worker_id)
    if worker is not None:
        db.delete(worker)
        db.commit()