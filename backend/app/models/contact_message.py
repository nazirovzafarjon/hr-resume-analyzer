"""SQLAlchemy model for messages sent through the landing page's Contact form.

The form is public (no account needed), so a row carries no user link — only
what the visitor typed. ``email`` is the address the team replies to.
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _utcnow() -> datetime:
    """Return the current UTC wall-clock time (timezone-aware)."""
    return datetime.now(timezone.utc)


class ContactMessage(Base):
    """A single Contact Us submission from the public landing site."""

    __tablename__ = "contact_messages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), index=True)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    message: Mapped[str] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )

    @property
    def name(self) -> str:
        """Full display name."""
        full = f"{self.first_name} {self.last_name}".strip()
        return full or self.email
