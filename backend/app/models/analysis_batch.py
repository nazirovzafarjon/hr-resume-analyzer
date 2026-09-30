"""SQLAlchemy model for auto-analyze batches (Auto Analyze on the Applications page)."""

import enum
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _utcnow() -> datetime:
    """Return the current UTC wall-clock time (timezone-aware)."""
    return datetime.now(timezone.utc)


class AnalysisBatchStatus(str, enum.Enum):
    """Status of an auto-analyze batch job."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class AnalysisBatch(Base):
    """Tracks a batch auto-analyze operation on multiple applications."""

    __tablename__ = "analysis_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # JSON array of application IDs in the order they should be processed
    application_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    # Current position in the application_ids list (index of next application to process)
    current_index: Mapped[int] = mapped_column(default=0, server_default="0")
    # Number of applications successfully analyzed
    successful_count: Mapped[int] = mapped_column(default=0, server_default="0")
    # Number of applications that failed analysis
    failed_count: Mapped[int] = mapped_column(default=0, server_default="0")
    # Number of applications skipped because they were no longer eligible when
    # their turn came (deleted, or analysed elsewhere in the meantime)
    skipped_count: Mapped[int] = mapped_column(default=0, server_default="0")
    # Currently processing application ID (for progress tracking)
    current_application_id: Mapped[int | None] = mapped_column(default=None, nullable=True)
    # Human-readable status
    status: Mapped[AnalysisBatchStatus] = mapped_column(
        Enum(
            AnalysisBatchStatus,
            name="analysis_batch_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=AnalysisBatchStatus.QUEUED,
        server_default=AnalysisBatchStatus.QUEUED.value,
    )
    # Timestamp when batch was created
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )
    # Timestamp when batch finished (completed, cancelled, or failed)
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    #: Total number of applications in this batch
    @property
    def total(self) -> int:
        return len(self.application_ids)

    #: Number of applications processed so far
    @property
    def processed(self) -> int:
        return self.successful_count + self.failed_count + self.skipped_count

    #: Remaining applications to process
    @property
    def remaining(self) -> int:
        return self.total - self.processed

    owner: Mapped["User"] = relationship(back_populates="analysis_batches")
