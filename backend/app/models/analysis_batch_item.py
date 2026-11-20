"""SQLAlchemy model for individual items within an auto-analyze batch."""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.analysis_batch import AnalysisBatch
    from app.models.application import Application


def _utcnow() -> datetime:
    """Return the current UTC wall-clock time (timezone-aware)."""
    return datetime.now(timezone.utc)


class BatchItemStatus(str, enum.Enum):
    """Processing status of an individual application item within an analysis batch."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class AnalysisBatchItem(Base):
    """Tracks the background execution and outcome of a single application inside a batch."""

    __tablename__ = "analysis_batch_items"
    __table_args__ = (
        UniqueConstraint("batch_id", "application_id", name="uq_batch_item_batch_application"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_batches.id", ondelete="CASCADE"), index=True
    )
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )
    celery_task_id: Mapped[str | None] = mapped_column(
        String(255), index=True, nullable=True
    )
    status: Mapped[BatchItemStatus] = mapped_column(
        Enum(
            BatchItemStatus,
            name="batch_item_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=BatchItemStatus.PENDING,
        server_default=BatchItemStatus.PENDING.value,
        index=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, server_default=func.now()
    )

    batch: Mapped[AnalysisBatch] = relationship(back_populates="items")
    application: Mapped[Application] = relationship()
