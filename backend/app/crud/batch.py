"""CRUD operations for analysis batches.

Contains only database access. Business logic belongs in services.
"""

from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.crud.query_utils import owner_filter
from app.models.analysis_batch import AnalysisBatch, AnalysisBatchStatus
from app.models.analysis_batch_item import AnalysisBatchItem, BatchItemStatus


def create_batch(
    db: Session,
    *,
    owner_id: int,
    application_ids: list[int],
) -> AnalysisBatch:
    """Create a new analysis batch and its item records in one atomic transaction."""
    batch = AnalysisBatch(
        owner_id=owner_id,
        application_ids=application_ids,
        status=AnalysisBatchStatus.QUEUED,
    )
    db.add(batch)
    db.flush()

    for app_id in application_ids:
        item = AnalysisBatchItem(
            batch_id=batch.id,
            application_id=app_id,
            status=BatchItemStatus.PENDING,
        )
        db.add(item)

    db.commit()
    db.refresh(batch)
    return batch


def get_batch(db: Session, batch_id: int, owner_id: int | None) -> AnalysisBatch | None:
    """Return the batch if it belongs to the owner (``None`` = any owner), else None."""
    return (
        db.execute(
            select(AnalysisBatch)
            .filter(AnalysisBatch.id == batch_id, owner_filter(AnalysisBatch.owner_id, owner_id))
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
    current_application_id: int | None = None,
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
    if current_application_id is not None:
        update_data["current_application_id"] = current_application_id
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

    # Mark all pending items as cancelled
    db.execute(
        update(AnalysisBatchItem)
        .where(
            AnalysisBatchItem.batch_id == batch.id,
            AnalysisBatchItem.status.in_([BatchItemStatus.PENDING, BatchItemStatus.RUNNING]),
        )
        .values(status=BatchItemStatus.CANCELLED)
    )

    return update_batch(
        db,
        batch,
        status=AnalysisBatchStatus.CANCELLED,
        finished_at=True,
    )


def get_batch_item(db: Session, item_id: int) -> AnalysisBatchItem | None:
    """Retrieve an AnalysisBatchItem by primary key."""
    return db.get(AnalysisBatchItem, item_id)


def get_batch_item_by_application(
    db: Session, batch_id: int, application_id: int
) -> AnalysisBatchItem | None:
    """Retrieve an AnalysisBatchItem by (batch_id, application_id)."""
    return (
        db.execute(
            select(AnalysisBatchItem).filter(
                AnalysisBatchItem.batch_id == batch_id,
                AnalysisBatchItem.application_id == application_id,
            )
        )
        .scalar_one_or_none()
    )


def update_batch_item(
    db: Session,
    item: AnalysisBatchItem,
    *,
    status: BatchItemStatus | None = None,
    celery_task_id: str | None = None,
    error_message: str | None = None,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> AnalysisBatchItem:
    """Update fields on an individual batch item."""
    if status is not None:
        item.status = status
    if celery_task_id is not None:
        item.celery_task_id = celery_task_id
    if error_message is not None:
        item.error_message = error_message
    if started_at is not None:
        item.started_at = started_at
    if completed_at is not None:
        item.completed_at = completed_at

    db.commit()
    db.refresh(item)
    return item


def increment_batch_counter(
    db: Session,
    batch_id: int,
    *,
    successful: bool = False,
    failed: bool = False,
    skipped: bool = False,
    current_application_id: int | None = None,
    current_index: int | None = None,
) -> None:
    """Atomically increment counters on an AnalysisBatch in PostgreSQL."""
    values: dict[object, object] = {}
    if successful:
        values[AnalysisBatch.successful_count] = AnalysisBatch.successful_count + 1
    if failed:
        values[AnalysisBatch.failed_count] = AnalysisBatch.failed_count + 1
    if skipped:
        values[AnalysisBatch.skipped_count] = AnalysisBatch.skipped_count + 1
    if current_application_id is not None:
        values[AnalysisBatch.current_application_id] = current_application_id
    if current_index is not None:
        values[AnalysisBatch.current_index] = current_index

    if values:
        db.execute(
            update(AnalysisBatch)
            .where(AnalysisBatch.id == batch_id)
            .values(values)
        )
        db.commit()


def check_and_complete_batch(db: Session, batch_id: int) -> bool:
    """Check if all items in a batch have finished, and if so mark batch COMPLETED."""
    batch = db.get(AnalysisBatch, batch_id)
    if not batch:
        return False
    if batch.status in (AnalysisBatchStatus.COMPLETED, AnalysisBatchStatus.CANCELLED):
        return True

    if batch.processed >= batch.total:
        batch.status = AnalysisBatchStatus.COMPLETED
        batch.finished_at = datetime.now(timezone.utc)
        batch.current_application_id = None
        db.commit()
        return True
    return False
