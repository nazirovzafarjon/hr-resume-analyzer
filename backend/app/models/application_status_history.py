"""SQLAlchemy model recording each change of an application's status.

Written by ``crud.application`` whenever an application is created or its
HR-owned ``application_status`` changes, so the Candidate Portal timeline can
show real dates instead of guessed ones. Applications that existed before this
table have no rows; their timeline steps simply carry no date.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ApplicationStatusHistory(Base):
    """One status an application entered, and when."""

    __tablename__ = "application_status_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )
    # ``ApplicationStatus`` value (stored as text so adding a status never
    # needs a second enum migration here).
    status: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    application: Mapped["Application"] = relationship(back_populates="status_history")
