"""SQLAlchemy model for server-side errors shown in the admin panel.

Only failures that reach the client as a 5xx are stored (unhandled exceptions,
database outages, upstream failures surfaced as 5xx). Full tracebacks stay in
the server log; a row keeps just enough to correlate with it: the request id,
endpoint, status and a short, scrubbed message. Request bodies are never
stored because they can carry passwords, tokens and resumes.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _utcnow() -> datetime:
    """Return the current UTC wall-clock time (timezone-aware)."""
    return datetime.now(timezone.utc)


class SystemErrorLog(Base):
    """One 5xx response produced by the API.

    Named ``SystemErrorLog`` rather than ``SystemError`` so it never shadows
    the Python builtin of that name.
    """

    __tablename__ = "system_errors"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(), index=True
    )
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    method: Mapped[str] = mapped_column(String(10))
    path: Mapped[str] = mapped_column(String(500))
    status_code: Mapped[int] = mapped_column(Integer, index=True)
    error_type: Mapped[str] = mapped_column(String(120))
    message: Mapped[str] = mapped_column(String(500), default="")
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
