"""SQLAlchemy model for HR-scheduled interviews.

An ``Interview`` links a candidate (``Application``) to the HR user who scheduled it.
The meeting link is a plain string that HR creates elsewhere (Zoom / Google Meet)
and pastes manually — there is no calendar integration involved.
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _utcnow() -> datetime:
    """Return the current UTC wall-clock time (timezone-aware)."""
    return datetime.now(timezone.utc)


class InterviewStatus(str, enum.Enum):
    """Lifecycle status of an interview."""

    UPCOMING = "upcoming"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Interview(Base):
    """A manual interview scheduled by an HR user for one of their candidates."""

    __tablename__ = "interviews"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )
    hr_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    interviewer: Mapped[str] = mapped_column(String(255))
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60)
    status: Mapped[InterviewStatus] = mapped_column(
        # Explicit name avoids a collision with the existing "interviewstatus"
        # enum type created by ``applications.interview_status``.
        Enum(
            InterviewStatus,
            name="interview_session_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=InterviewStatus.UPCOMING,
    )
    meeting_link: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        server_default=func.now(),
        onupdate=_utcnow,
    )

    candidate: Mapped["Application"] = relationship(back_populates="interviews")
    hr: Mapped["User"] = relationship(back_populates="interviews")