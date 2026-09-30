"""SQLAlchemy model for AI analysis attempts (admin AI monitoring).

``applications`` only keeps the *latest* analysis state of an application, so a
failure is overwritten by the next successful retry and provider problems
leave no history. One row here is written per provider attempt (application
screening or vacancy extraction), successful or not, which is what the AI
monitoring page aggregates: success rate, duration, failures by category.

Everything stored is safe to show an administrator: provider name, model id,
whether the platform or the HR user's own key was used, a normalized error
category and the user-facing error message. API keys, prompts, resume text and
raw provider payloads are never stored.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _utcnow() -> datetime:
    """Return the current UTC wall-clock time (timezone-aware)."""
    return datetime.now(timezone.utc)


class AIAnalysisRun(Base):
    """A single AI provider attempt and its outcome."""

    __tablename__ = "ai_analysis_runs"
    __table_args__ = (
        # Monitoring filters by outcome and always orders by time.
        Index("ix_ai_analysis_runs_status_created_at", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(), index=True
    )
    #: "application" (resume screening) or "vacancy" (job text extraction).
    kind: Mapped[str] = mapped_column(String(20))
    #: "completed" or "failed".
    status: Mapped[str] = mapped_column(String(20))
    # SET NULL keeps the monitoring history when an application, job or
    # account is deleted.
    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    job_id: Mapped[int | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True
    )
    application_id: Mapped[int | None] = mapped_column(
        ForeignKey("applications.id", ondelete="SET NULL"), nullable=True
    )
    provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    #: "default" (platform key) or "custom" (the HR user's own key).
    source: Mapped[str | None] = mapped_column(String(16), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    #: HTTP status the API reported for the failure (e.g. 429, 502, 503).
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
