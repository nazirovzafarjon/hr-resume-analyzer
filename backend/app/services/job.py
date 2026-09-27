"""Job business logic (anything more complex than simple CRUD)."""

from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

from app.crud.job import get_job
from app.models.job import Job
from app.models.worker import Worker

# Mapping exposed analytics category names to groupable Job columns.
# "experience" is accepted as an alias of "required_experience" because the
# frontend's groupBy control sends the shorter, user-facing value.
_GROUPABLE_COLUMNS = {
    "company": Job.company_name,
    "position": Job.position,
    "required_experience": Job.required_experience,
    "experience": Job.required_experience,
}


def increment_leads_count(db: Session, job_id: int) -> Job | None:
    """Increment a job's lead count by one and return the refreshed job."""
    job = get_job(db, job_id)
    if job is None:
        return None

    job.leads_count += 1
    db.commit()
    db.refresh(job)
    return job


def job_analytics(db: Session, owner_id: int, category: str = "company") -> dict:
    """Return high-level hiring analytics grouped by the given category.

    Args:
        owner_id: The HR user whose jobs/candidates are analysed.
        category: One of ``company``, ``position`` or ``required_experience``.

    Raises:
        ValueError: If ``category`` is not a supported grouping.
    """
    group_column = _GROUPABLE_COLUMNS.get(category)
    if group_column is None:
        raise ValueError(f"Unsupported analytics category: {category}")

    total_jobs = (
        db.query(func.count(Job.id)).filter(Job.owner_id == owner_id).scalar() or 0
    )
    total_candidates = (
        db.query(func.count(Worker.id))
        .join(Job, Worker.job_id == Job.id)
        .filter(Job.owner_id == owner_id)
        .scalar()
        or 0
    )
    total_leads = (
        db.query(func.coalesce(func.sum(Job.leads_count), 0))
        .filter(Job.owner_id == owner_id)
        .scalar()
        or 0
    )

    rows = (
        db.query(
            group_column,
            func.count(distinct(Job.id)).label("jobs"),
            func.count(Worker.id).label("candidates"),
        )
        .outerjoin(Worker, Worker.job_id == Job.id)
        .filter(Job.owner_id == owner_id)
        .group_by(group_column)
        .order_by(group_column)
        .all()
    )
    breakdown = [
        {"category": str(value), "jobs": jobs, "candidates": candidates}
        for value, jobs, candidates in rows
    ]

    return {
        "total_jobs": total_jobs,
        "total_candidates": total_candidates,
        "total_leads": total_leads,
        "group_by": category,
        "breakdown": breakdown,
    }