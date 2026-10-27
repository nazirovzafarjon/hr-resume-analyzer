"""SQLAlchemy model for pending HR account registrations.

In two-phase registration, an HR account is stored here until the email is
confirmed. No row exists in ``users`` and no session tokens are issued until
verification succeeds.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PendingRegistration(Base):
    """Temporary storage for an unverified HR registration."""

    __tablename__ = "pending_registrations"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    #: sha256 hex digest of the 32-byte URL verification token
    token_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    #: bcrypt hash of optional 6-digit backup code
    code_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)

    @property
    def is_consumed(self) -> bool:
        return self.consumed_at is not None

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at
