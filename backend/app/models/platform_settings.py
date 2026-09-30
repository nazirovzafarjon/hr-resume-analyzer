"""SQLAlchemy model for runtime platform settings editable by admins.

Deliberately tiny: secrets and infrastructure configuration stay in the
environment (``app.core.config``) and are never editable from the browser.
Only switches that an administrator legitimately flips at runtime live here.
The table holds a single row (``id = 1``), created on first read.
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _utcnow() -> datetime:
    """Return the current UTC wall-clock time (timezone-aware)."""
    return datetime.now(timezone.utc)


class PlatformSettings(Base):
    """Singleton row of runtime platform switches."""

    __tablename__ = "platform_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    #: When False, new accounts cannot be created (password sign-up and
    #: first-time Google sign-in). Existing users keep signing in.
    registration_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        server_default=func.now(),
        onupdate=_utcnow,
    )
    updated_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
