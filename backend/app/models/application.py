"""SQLAlchemy model for job applications (and the candidates they become).

An ``Application`` belongs to a ``Job`` and is one candidate submission. The record carries submission timing, the HR-controlled pipeline
statuses and the AI screening result (``ai_score`` + ``ai_analysis_details``).

Pipeline model
--------------
``application_status`` / ``analysis_status`` describe the *application* stage;
``candidate_at`` marks the moment HR moved the application into the hiring
pipeline (after which it is a "Candidate" in the UI). ``hiring_status`` and
``interview_status`` are the HR/interviewer-owned candidate fields and are
never written by the AI. One row per application means an application can
never produce more than one candidate.
"""

import enum
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

# Imported for the type annotation below (SQLAlchemy resolves it lazily).
from app.models.application_form import ApplicationResponse  # noqa: F401


def _utcnow() -> datetime:
    """Return the current UTC wall-clock time (timezone-aware)."""
    return datetime.now(timezone.utc)


class HiringStatus(str, enum.Enum):
    """Hiring decision for a candidate (HR-owned, never set by the AI)."""

    STRONG_HIRE = "strong_hire"
    HIRE = "hire"
    WEAK_HIRE = "weak_hire"
    DO_NOT_HIRE = "do_not_hire"


class InterviewStatus(str, enum.Enum):
    """Interview progress for a candidate (HR/interviewer-owned)."""

    IN_PROCESS = "in_process"
    COMPLETED = "completed"
    NOT_COMPLETED = "not_completed"


class ApplicationStatus(str, enum.Enum):
    """HR-reviewed pipeline status of a submitted application."""

    NEW = "new"
    REVIEWING = "reviewing"
    SHORTLISTED = "shortlisted"
    INTERVIEW = "interview"
    # Final positive decision (the candidate sees "Application accepted").
    HIRED = "hired"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class AnalysisStatus(str, enum.Enum):
    """AI processing state of an application.

    Independent of :class:`ApplicationStatus`: an application can be
    "shortlisted" while its analysis is still "pending", or "failed" while HR
    keeps reviewing the submitted information by hand.

    ``NEW`` is used for applications that have never been analyzed.
    ``PENDING`` is kept for backward compatibility with existing data.
    """

    NEW = "new"
    PENDING = "pending"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"


class Application(Base):
    """A candidate/application applying for a job."""

    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), index=True
    )
    # Candidate Portal account that submitted this application while signed in
    # (None for guest submissions and HR-entered applications). Deleting the
    # account keeps the application for HR.
    candidate_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("candidate_accounts.id", ondelete="SET NULL"), index=True, nullable=True
    )
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255))
    resume_path: Mapped[str] = mapped_column(String(500), default="")
    # AI screening result: overall suitability score (0-100) and the detailed
    # analysis payload (match percentage, matched/missing requirements and
    # skills, strengths, weaknesses, risks, summaries, AI recommendation).
    ai_score: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    ai_analysis_details: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )
    # HR-owned application pipeline status (AI never changes it).
    application_status: Mapped[ApplicationStatus] = mapped_column(
        # Explicit type name keeps this enum from colliding with any other
        # status enum created on the same database.
        Enum(
            ApplicationStatus,
            name="application_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=ApplicationStatus.NEW,
        server_default=ApplicationStatus.NEW.value,
    )
    # AI processing state (independent of ``application_status``).
    analysis_status: Mapped[AnalysisStatus] = mapped_column(
        Enum(
            AnalysisStatus,
            name="application_analysis_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=AnalysisStatus.NEW,
        server_default=AnalysisStatus.NEW.value,
    )
    # Safe, user-facing reason why the last analysis attempt failed (never the
    # raw provider payload / credentials).
    analysis_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # When the current analysis run started; used to detect a run that was
    # interrupted (server restart) so HR can retry instead of being blocked.
    analysis_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    hiring_status: Mapped[HiringStatus] = mapped_column(
        Enum(HiringStatus, values_callable=lambda x: [e.value for e in x]),
        default=HiringStatus.HIRE,
    )
    interview_status: Mapped[InterviewStatus] = mapped_column(
        Enum(InterviewStatus, values_callable=lambda x: [e.value for e in x]),
        default=InterviewStatus.NOT_COMPLETED,
    )
    # Set when HR moves the application into the hiring pipeline ("candidate").
    candidate_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # ``created_at`` is the record's creation time; ``submitted_at`` is the
    # application submission time surfaced by the Applications UI.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )

    @property
    def is_candidate(self) -> bool:
        """True once HR has moved this application into the candidate pipeline."""
        return self.candidate_at is not None

    @property
    def company_name(self) -> str:
        """Company name from the associated job."""
        return self.job.company_name if self.job else ""

    @property
    def position(self) -> str:
        """Position name from the associated job."""
        return self.job.position if self.job else ""

    job: Mapped["Job"] = relationship(back_populates="applications")
    candidate_account: Mapped["CandidateAccount | None"] = relationship(
        back_populates="applications"
    )
    status_history: Mapped[list["ApplicationStatusHistory"]] = relationship(
        back_populates="application",
        passive_deletes=True,
        order_by="ApplicationStatusHistory.created_at, ApplicationStatusHistory.id",
    )
    interviews: Mapped[list["Interview"]] = relationship(
        back_populates="candidate", passive_deletes=True
    )
    # Structured answers submitted through the public application form
    # (one-to-one; ``None`` for manually recorded candidates).
    application_response: Mapped["ApplicationResponse | None"] = relationship(
        back_populates="application", uselist=False, passive_deletes=True
    )
