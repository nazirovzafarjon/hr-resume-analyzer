"""SQLAlchemy model for emailed 6-digit verification codes.

A verification code is short-lived and must never be stored in plain text, so
each request creates one row holding only a **bcrypt hash** of the code plus its
expiry, attempt count and used-at marker. Service logic lives in
``app.services.email_verification``; database access in
``app.crud.email_verification``.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EmailVerification(Base):
    """One issued verification code for an HR user account."""

    __tablename__ = "email_verifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    #: bcrypt digest of the 6-digit code — the raw code is never stored.
    code_hash: Mapped[str] = mapped_column(String(255))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    #: Wrong-code attempts so far; reaching the configured maximum invalidates
    #: the code (``used_at`` is set too).
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    #: Set when the code is consumed or invalidated; a non-null value means the
    #: code can no longer verify (single use).
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    @property
    def is_used(self) -> bool:
        return self.used_at is not None
