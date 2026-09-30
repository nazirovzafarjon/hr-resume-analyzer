"""Database access for AI analysis attempts (insert and read only)."""

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.crud.query_utils import paginate
from app.models.ai_analysis_run import AIAnalysisRun
from app.models.job import Job
from app.models.user import User


def create_run(db: Session, **values: Any) -> AIAnalysisRun:
    """Insert one run row and commit."""
    run = AIAnalysisRun(**values)
    db.add(run)
    db.commit()
    return run


def list_runs(
    db: Session,
    *,
    page: int,
    limit: int,
    status: str | None = None,
    kind: str | None = None,
    provider: str | None = None,
    error_category: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> tuple[list[Any], int]:
    """Return one page of runs with their owner email and job title.

    Rows are ``(AIAnalysisRun, owner_email, position, company_name)``; the
    outer joins keep runs whose job or owner has since been deleted.
    """
    stmt = (
        select(AIAnalysisRun, User.email, Job.position, Job.company_name)
        .outerjoin(User, User.id == AIAnalysisRun.owner_id)
        .outerjoin(Job, Job.id == AIAnalysisRun.job_id)
    )
    if status:
        stmt = stmt.where(AIAnalysisRun.status == status)
    if kind:
        stmt = stmt.where(AIAnalysisRun.kind == kind)
    if provider:
        stmt = stmt.where(AIAnalysisRun.provider == provider)
    if error_category:
        stmt = stmt.where(AIAnalysisRun.error_category == error_category)
    if date_from is not None:
        stmt = stmt.where(AIAnalysisRun.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(AIAnalysisRun.created_at <= date_to)
    stmt = stmt.order_by(AIAnalysisRun.created_at.desc(), AIAnalysisRun.id.desc())
    return paginate(db, stmt, page, limit)


def outcome_summary(db: Session, since: datetime | None = None) -> dict[str, Any]:
    """Totals, failures and average duration, optionally since a moment."""
    stmt = select(
        func.count(AIAnalysisRun.id),
        func.count(AIAnalysisRun.id).filter(AIAnalysisRun.status == "completed"),
        func.count(AIAnalysisRun.id).filter(AIAnalysisRun.status == "failed"),
        func.avg(AIAnalysisRun.duration_ms).filter(AIAnalysisRun.status == "completed"),
    )
    if since is not None:
        stmt = stmt.where(AIAnalysisRun.created_at >= since)
    total, completed, failed, avg_duration = db.execute(stmt).one()
    return {
        "total": int(total or 0),
        "completed": int(completed or 0),
        "failed": int(failed or 0),
        "avg_duration_ms": round(float(avg_duration)) if avg_duration is not None else None,
    }


def grouped_counts(db: Session, column: Any, *, status: str | None = None) -> list[tuple[Any, int]]:
    """Run counts grouped by one column (provider, error category, ...)."""
    stmt = select(column, func.count(AIAnalysisRun.id)).group_by(column)
    if status:
        stmt = stmt.where(AIAnalysisRun.status == status)
    stmt = stmt.order_by(func.count(AIAnalysisRun.id).desc())
    return [(value, int(count)) for value, count in db.execute(stmt).all()]
