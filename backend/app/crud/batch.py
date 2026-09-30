"""CRUD operations for analysis batches.

Contains only database access. Business logic belongs in services.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.worker import AnalysisBatch, AnalysisBatchStatus


def create_batch(
    db: Session,
    *,
    owner_id: int,
    worker_ids: list[int],
) -> AnalysisBatch:
    """Create a new analysis batch and return it."""
    batch = AnalysisBatch(
        owner_id=owner_id,
        worker_ids=worker_ids,
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


def get_batch(db: Session, batch_id: int, owner_id: int) -> AnalysisBatch | None:
    """Return the batch if it belongs to the owner, else None."""
    return (
        db.execute(
            select(AnalysisBatch)
            .filter(AnalysisBatch.id == batch_id, AnalysisBatch.owner_id == owner_id)
        )
        .scalar_one_or_none()
    )


def get_batch_by_id(db: Session, batch_id: int) -> AnalysisBatch | None:
    """Return the batch by ID without ownership check (for internal use)."""
    return db.get(AnalysisBatch, batch_id)


def update_batch(
    db: Session,
    batch: AnalysisBatch,
    *,
    status: AnalysisBatchStatus | None = None,
    current_index: int | None = None,
    successful_count: int | None = None,
    failed_count: int | None = None,
    skipped_count: int | None = None,
    current_worker_id: int | None = None,
    finished_at: bool = False,
) -> AnalysisBatch:
    """Update batch fields and return the refreshed instance."""
    update_data: dict[str, object] = {}
    if status is not None:
        update_data["status"] = status
    if current_index is not None:
        update_data["current_index"] = current_index
    if successful_count is not None:
        update_data["successful_count"] = successful_count
    if failed_count is not None:
        update_data["failed_count"] = failed_count
    if skipped_count is not None:
        update_data["skipped_count"] = skipped_count
    if current_worker_id is not None:
        update_data["current_worker_id"] = current_worker_id
    if finished_at:
        from datetime import datetime, timezone

        update_data["finished_at"] = datetime.now(timezone.utc)

    for field, value in update_data.items():
        setattr(batch, field, value)

    db.commit()
    db.refresh(batch)
    return batch


def cancel_batch(db: Session, batch: AnalysisBatch) -> AnalysisBatch:
    """Cancel a batch if it's still running or queued."""
    if batch.status not in (AnalysisBatchStatus.QUEUED, AnalysisBatchStatus.RUNNING):
        return batch  # Already finished, no-op

    return update_batch(
        db,
        batch,
        status=AnalysisBatchStatus.CANCELLED,
        finished_at=True,
    )
