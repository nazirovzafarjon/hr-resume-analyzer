"""Database access for the audit trail (insert and read only).

There is intentionally no update or delete function: audit rows are
append-only and no API can rewrite history.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.crud.query_utils import contains_pattern, paginate
from app.models.audit_log import AuditLog


def create_entry(db: Session, **values: Any) -> AuditLog:
    """Insert one audit row and commit."""
    entry = AuditLog(**values)
    db.add(entry)
    db.commit()
    return entry


def list_entries(
    db: Session,
    *,
    page: int,
    limit: int,
    search: str | None = None,
    actor_user_id: int | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> tuple[list[AuditLog], int]:
    """Return one page of audit rows (newest first) plus the filtered total."""
    stmt = select(AuditLog)
    if search:
        pattern = contains_pattern(search)
        stmt = stmt.where(
            or_(
                AuditLog.actor_email.ilike(pattern, escape="\\"),
                AuditLog.action.ilike(pattern, escape="\\"),
                AuditLog.resource_id.ilike(pattern, escape="\\"),
                AuditLog.request_id.ilike(pattern, escape="\\"),
            )
        )
    if actor_user_id is not None:
        stmt = stmt.where(AuditLog.actor_user_id == actor_user_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
    if date_from is not None:
        stmt = stmt.where(AuditLog.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(AuditLog.created_at <= date_to)
    stmt = stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
    rows, total = paginate(db, stmt, page, limit)
    return [row[0] for row in rows], total


def recent_entries(
    db: Session,
    limit: int,
    *,
    actor_user_id: int | None = None,
    exclude_actions: tuple[str, ...] = (),
) -> list[AuditLog]:
    """Return the newest audit rows (for activity feeds)."""
    stmt = select(AuditLog)
    if actor_user_id is not None:
        stmt = stmt.where(AuditLog.actor_user_id == actor_user_id)
    if exclude_actions:
        stmt = stmt.where(AuditLog.action.not_in(exclude_actions))
    stmt = stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit)
    return list(db.execute(stmt).scalars())
