"""Database access for recorded 5xx errors (insert and read only)."""

from datetime import datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.crud.query_utils import contains_pattern, paginate
from app.models.system_error import SystemErrorLog


def create_error(db: Session, **values: Any) -> SystemErrorLog:
    """Insert one error row and commit."""
    entry = SystemErrorLog(**values)
    db.add(entry)
    db.commit()
    return entry


def list_errors(
    db: Session,
    *,
    page: int,
    limit: int,
    search: str | None = None,
    status_code: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> tuple[list[SystemErrorLog], int]:
    """Return one page of errors (newest first) plus the filtered total."""
    stmt = select(SystemErrorLog)
    if search:
        pattern = contains_pattern(search)
        stmt = stmt.where(
            or_(
                SystemErrorLog.path.ilike(pattern, escape="\\"),
                SystemErrorLog.error_type.ilike(pattern, escape="\\"),
                SystemErrorLog.message.ilike(pattern, escape="\\"),
                SystemErrorLog.request_id.ilike(pattern, escape="\\"),
            )
        )
    if status_code is not None:
        stmt = stmt.where(SystemErrorLog.status_code == status_code)
    if date_from is not None:
        stmt = stmt.where(SystemErrorLog.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(SystemErrorLog.created_at <= date_to)
    stmt = stmt.order_by(SystemErrorLog.created_at.desc(), SystemErrorLog.id.desc())
    rows, total = paginate(db, stmt, page, limit)
    return [row[0] for row in rows], total


def count_since(db: Session, since: datetime) -> int:
    """Number of errors recorded at or after ``since``."""
    return db.execute(
        select(func.count(SystemErrorLog.id)).where(SystemErrorLog.created_at >= since)
    ).scalar_one()


def status_code_counts(db: Session, since: datetime) -> dict[int, int]:
    """Errors per HTTP status recorded at or after ``since``."""
    rows = db.execute(
        select(SystemErrorLog.status_code, func.count(SystemErrorLog.id))
        .where(SystemErrorLog.created_at >= since)
        .group_by(SystemErrorLog.status_code)
    ).all()
    return {int(code): int(count) for code, count in rows}
