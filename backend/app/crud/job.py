"""CRUD operations for jobs.

Contains only database access. Business logic belongs in services.
"""

import uuid
from sqlalchemy.orm import Session, selectinload

from app.crud.query_utils import owner_filter
from app.models.job import Job
from app.schemas.job import JobCreate, JobUpdate


def create_job(db: Session, owner_id: int, payload: JobCreate) -> Job:
    """Create and return a new job owned by the given HR user.

    ``payload.application_form`` is not a Job column — the router persists it
    through the application-form service after the job row exists.
    """
    job = Job(owner_id=owner_id, **payload.model_dump(exclude={"application_form"}))
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_job(db: Session, job_id: int) -> Job | None:
    """Return the job with the given id, or ``None`` if it does not exist."""
    return db.get(Job, job_id)


def get_job_by_public_id(db: Session, public_id: uuid.UUID) -> Job | None:
    """Return the job with the given public_id, or ``None`` if it does not exist."""
    return db.query(Job).filter(Job.public_id == public_id).first()


def get_jobs_for_user(db: Session, owner_id: int | None) -> list[Job]:
    """Return all jobs created by a given HR user, newest first.

    ``owner_id=None`` (an admin session) returns every HR user's jobs.

    Eager-loads each job's application form so responses can embed the
    public link configuration without N+1 queries.
    """
    return (
        db.query(Job)
        .options(selectinload(Job.application_form))
        .filter(owner_filter(Job.owner_id, owner_id))
        .order_by(Job.created_at.desc())
        .all()
    )


def get_recent_jobs(db: Session, owner_id: int | None, limit: int = 5) -> list[Job]:
    """Return the most recently created jobs for a given HR user (``None`` = all)."""
    return (
        db.query(Job)
        .options(selectinload(Job.application_form))
        .filter(owner_filter(Job.owner_id, owner_id))
        .order_by(Job.created_at.desc())
        .limit(limit)
        .all()
    )


def update_job(db: Session, job: Job, payload: JobUpdate) -> Job:
    """Apply the submitted updates to a job and return the refreshed instance."""
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(job, field, value)
    db.commit()
    db.refresh(job)
    return job


def delete_job(db: Session, job_id: int) -> None:
    """Delete the job with the given id, if it exists."""
    job = db.get(Job, job_id)
    if job is not None:
        db.delete(job)
        db.commit()