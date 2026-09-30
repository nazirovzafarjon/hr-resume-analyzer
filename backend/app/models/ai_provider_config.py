"""SQLAlchemy model for an HR user's own AI provider credentials.

Set in Settings -> "Connect your provider and API key". When a user has an
active row, every AI operation on their data uses it instead of the platform
provider from the environment. One row per user (unique ``user_id``).

The API key is stored only encrypted (see ``app.core.encryption``); the last
four characters are kept separately so the UI can show a masked hint
without decrypting anything.
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _utcnow() -> datetime:
    """Return the current UTC wall-clock time (timezone-aware)."""
    return datetime.now(timezone.utc)


class UserAIProviderConfig(Base):
    """One HR user's custom AI provider, API key and model."""

    __tablename__ = "user_ai_provider_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    provider: Mapped[str] = mapped_column(String(32))
    api_key_encrypted: Mapped[str] = mapped_column(Text)
    api_key_last4: Mapped[str] = mapped_column(String(4))
    model_id: Mapped[str] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        server_default=func.now(),
        onupdate=_utcnow,
    )
