"""SQLAlchemy models for invalidating already-issued JWTs.

Stored in PostgreSQL (not process memory) so revocations survive restarts and
are shared by every API worker. See ``app.core.token_registry`` for the rules.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _utcnow() -> datetime:
    """Return the current UTC wall-clock time (timezone-aware)."""
    return datetime.now(timezone.utc)


class RevokedToken(Base):
    """A single token (by ``jti``) that was consumed or revoked.

    Rows are only needed until the token would have expired anyway, so
    ``expires_at`` is indexed for cheap pruning.
    """

    __tablename__ = "revoked_tokens"

    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )


class SessionCutoff(Base):
    """Per-user instant before which every issued token is rejected.

    Written when a password is changed or reset ("sign out everywhere").
    Deleted with the user.
    """

    __tablename__ = "session_cutoffs"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    cutoff: Mapped[datetime] = mapped_column(DateTime(timezone=True))
