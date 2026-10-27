"""SQLAlchemy model for HR users.

Initial structure only. Relationships reference other models by name and
will be resolved once those models are finalized.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    """An HR user account."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    # Nullable: users who sign in with Google never have a password.
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str] = mapped_column(String(255))
    # Google OAuth profile info (present only for "Continue with Google" accounts).
    google_id: Mapped[str | None] = mapped_column(
        String(255), unique=True, index=True, nullable=True
    )
    picture: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # Server-relative URL of the user's uploaded profile image
    # (e.g. "/uploads/profile/<uuid>.jpg"), or None when unset.
    profile_image: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # Email verification gate. New password registrations start unverified and
    # cannot use the HR/admin panel until they confirm their address; accounts
    # created before this column existed are grandfathered as verified.
    is_email_verified: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    # Registration time. Accounts that existed before this column was added
    # carry the migration's timestamp instead (the real date was never stored).
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    # Last successful sign-in (password, Google, reset link or token refresh).
    # Shown to admins as "last activity"; None until the user signs in again.
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    @property
    def has_password(self) -> bool:
        """True when the account has a local password (false for Google-only)."""
        return self.hashed_password is not None

    # passive_deletes: let the database ON DELETE CASCADE remove a user's jobs
    # when the user is deleted. Without it the ORM tries to set the child FK to
    # NULL, which fails because jobs.owner_id is NOT NULL.
    jobs: Mapped[list["Job"]] = relationship(
        back_populates="owner", passive_deletes=True
    )
    interviews: Mapped[list["Interview"]] = relationship(
        back_populates="hr", passive_deletes=True
    )
    analysis_batches: Mapped[list["AnalysisBatch"]] = relationship(
        back_populates="owner", passive_deletes=True
    )