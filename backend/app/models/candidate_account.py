"""SQLAlchemy model for candidate (job seeker) accounts — the Candidate Portal.

Architecture decision
---------------------
Candidates get their **own table and their own token purposes** instead of a
role on ``users``:

* ``users`` is the HR/admin identity. Every HR endpoint resolves its caller
  through ``dependencies.auth.get_current_session``, which accepts only
  ``typ=access`` tokens. Candidate tokens carry ``typ=candidate_access``, so
  they are rejected by every HR endpoint without touching those endpoints.
* The same person may be both an HR user and a candidate with one email.
* Password hashing and JWT signing are shared (``core.security``); only the
  identity table and the token purposes are separate.

A candidate account is linked to the ``Application`` rows it submitted while
signed in (``applications.candidate_account_id``). Applications are never
linked by matching email: emails are not verified, so that would let anyone
read another person's applications and CV.

TODO(CANDIDATE-PORTAL): future phases (candidate <-> HR messaging, a candidate
AI assistant, interview confirmation/rescheduling, notifications) should hang
off ``Application`` / ``Interview`` or get their own tables that reference
this account. Keep HR-only data (hiring recommendation, interviewer notes,
internal AI text) out of anything a candidate can read.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CandidateAccount(Base):
    """A job seeker's account for the Candidate Portal."""

    __tablename__ = "candidate_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Server-relative URL of the uploaded profile image, or None.
    profile_image: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    # Tokens issued before this instant are rejected ("sign out everywhere"
    # after a password change or reset).
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    applications: Mapped[list["Application"]] = relationship(
        back_populates="candidate_account", passive_deletes=True
    )
