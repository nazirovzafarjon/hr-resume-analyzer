"""SQLAlchemy model for the platform audit trail.

One row per meaningful action (sign-ins, job/application/interview changes,
AI analysis outcomes and every administrative mutation). Rows are written by
``app.services.audit`` and are append-only: no API updates or deletes them.

``actor_email`` is a snapshot taken at write time, so the trail stays readable
after the actor's account is renamed or deleted (``actor_user_id`` is then set
to NULL by the foreign key instead of deleting history).
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _utcnow() -> datetime:
    """Return the current UTC wall-clock time (timezone-aware)."""
    return datetime.now(timezone.utc)


class AuditLog(Base):
    """A single audited action."""

    __tablename__ = "audit_logs"
    # The admin page always lists newest first, usually narrowed by action or
    # resource type, so those filters get composite indexes with created_at.
    __table_args__ = (
        Index("ix_audit_logs_action_created_at", "action", "created_at"),
        Index("ix_audit_logs_resource_created_at", "resource_type", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(), index=True
    )
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    actor_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    action: Mapped[str] = mapped_column(String(64))
    resource_type: Mapped[str] = mapped_column(String(32))
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Small, sanitized context (changed field names, counts, statuses). Never
    # credentials, tokens or document contents -- see audit.sanitize_metadata.
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
