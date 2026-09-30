"""Auto-analyze batch service for processing multiple applications.

Provides the business logic for:
- Counting eligible applications (new and never analysed), with optional
  company/position/job filters applied in SQL
- Creating analysis batches
- Running batch analysis one-by-one in background
- Tracking progress
- Canceling batches
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.crud import batch as batch_crud
from app.crud import worker as worker_crud
from app.models.job import Job
from app.models.user import User
from app.models.worker import (
    AnalysisBatch,
    AnalysisBatchStatus,
    AnalysisStatus,
    ApplicationStatus,
    Worker,
)
from app.services import application_analysis as single_analysis
from app.services.ai.application_analyzer import analyze_application as ai_analyze
from app.services.ai.job_analyzer import AIServiceError
from app.services.resume_text import extract_resume_text

logger = logging.getLogger(__name__)

#: Maximum number of resumes that can be analyzed in a single batch
MAX_BATCH_SIZE = 1000

#: Minimum number of resumes that can be analyzed in a single batch
MIN_BATCH_SIZE = 1


class AutoAnalyzeError(Exception):
    """Base exception for auto-analyze errors."""

    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class InvalidBatchSizeError(AutoAnalyzeError):
    """Raised when the batch size is out of valid range."""

    def __init__(self, message: str = "Invalid batch size"):
        super().__init__(message, status_code=422)


class NoAvailableApplicationsError(AutoAnalyzeError):
    """Raised when there are no NEW applications to analyze."""

    def __init__(self, message: str = "No new applications available"):
        super().__init__(message, status_code=400)


class BatchNotFoundError(AutoAnalyzeError):
    """Raised when a batch ID is not found or not owned by the user."""

    def __init__(self, message: str = "Batch not found"):
        super().__init__(message, status_code=404)


def _utcnow() -> datetime:
    """Return the current UTC wall-clock time (timezone-aware)."""
    return datetime.now(timezone.utc)


#: Never-analysed states (``PENDING`` is the legacy spelling of ``NEW``).
#: Completed, running and failed analyses are not picked up automatically;
#: HR retries a failed one from the application itself.
ELIGIBLE_ANALYSIS_STATUSES = (AnalysisStatus.NEW, AnalysisStatus.PENDING)


def _eligible_filter(
    owner_id: int,
    *,
    job_id: int | None = None,
    company: str | None = None,
    position: str | None = None,
) -> list:
    """SQL conditions for applications Auto Analyze may pick.

    Owned by the HR user, still ``application_status = new`` and never
    analysed. ``None`` filters ("All") add no condition.
    """
    conditions = [
        Job.owner_id == owner_id,
        Worker.application_status == ApplicationStatus.NEW,
        Worker.analysis_status.in_(ELIGIBLE_ANALYSIS_STATUSES),
    ]
    if job_id is not None:
        conditions.append(Worker.job_id == job_id)
    if company is not None:
        conditions.append(Job.company_name == company)
    if position is not None:
        conditions.append(Job.position == position)
    return conditions


def _get_eligible_worker_ids(
    db: Session,
    owner_id: int,
    *,
    order: str = "oldest",
    limit: int | None = None,
    job_id: int | None = None,
    company: str | None = None,
    position: str | None = None,
) -> list[int]:
    """Return IDs of eligible applications, ordered and limited in PostgreSQL.

    Args:
        db: Database session.
        owner_id: The HR user's ID (for ownership scoping).
        order: "oldest" for created_at ASC, "newest" for created_at DESC.
        limit: Maximum number of worker IDs to return (None for unlimited).
        job_id / company / position: Optional filters (``None`` = all).
    """
    query = (
        select(Worker.id)
        .join(Worker.job)
        .where(*_eligible_filter(owner_id, job_id=job_id, company=company, position=position))
    )

    # Ordering: created_at ASC/DESC, then id for determinism
    if order == "newest":
        query = query.order_by(Worker.created_at.desc(), Worker.id.desc())
    else:  # oldest (default)
        query = query.order_by(Worker.created_at.asc(), Worker.id.asc())

    if limit is not None:
        query = query.limit(limit)

    return list(db.execute(query).scalars().all())


def get_available_new_count(
    db: Session,
    owner_id: int,
    *,
    job_id: int | None = None,
    company: str | None = None,
    position: str | None = None,
) -> int:
    """Count eligible applications (a COUNT query; no rows are loaded)."""
    query = (
        select(func.count(Worker.id))
        .join(Worker.job)
        .where(*_eligible_filter(owner_id, job_id=job_id, company=company, position=position))
    )
    return db.execute(query).scalar_one()


def get_filter_options(db: Session, owner_id: int) -> list[dict[str, Any]]:
    """Company/position pairs that currently have eligible applications.

    Feeds the Company and Position dropdowns, with the number of eligible
    applications per pair, so HR only sees choices that can select something.
    """
    query = (
        select(Job.company_name, Job.position, func.count(Worker.id))
        .join(Worker.job)
        .where(*_eligible_filter(owner_id))
        .group_by(Job.company_name, Job.position)
        .order_by(Job.company_name, Job.position)
    )
    return [
        {"company_name": company, "position": position, "count": count}
        for company, position, count in db.execute(query).all()
    ]


def create_auto_analyze_batch(
    db: Session,
    current_user: User,
    *,
    count: int,
    order: str = "oldest",
    job_id: int | None = None,
    company: str | None = None,
    position: str | None = None,
) -> AnalysisBatch:
    """Create a new auto-analyze batch and return it.

    This selects the eligible NEW applications, creates a batch record,
    and returns it. The actual analysis runs in the background.

    Args:
        db: Database session.
        current_user: The authenticated HR user.
        count: Number of applications to analyze (1-1000).
        order: "oldest" or "newest" for processing order.
        job_id: Optional job filter.

    Returns:
        The created AnalysisBatch.

    Raises:
        InvalidBatchSizeError: If count is not in 1-1000 range.
        NoAvailableApplicationsError: If no NEW applications are available.
    """
    # Validate count
    if not isinstance(count, int) or count < MIN_BATCH_SIZE or count > MAX_BATCH_SIZE:
        raise InvalidBatchSizeError(
            f"Batch size must be between {MIN_BATCH_SIZE} and {MAX_BATCH_SIZE}."
        )

    if order not in ("oldest", "newest"):
        raise AutoAnalyzeError("Order must be 'oldest' or 'newest'.", status_code=422)

    # Get eligible worker IDs
    worker_ids = _get_eligible_worker_ids(
        db,
        current_user.id,
        order=order,
        limit=count,
        job_id=job_id,
        company=company,
        position=position,
    )

    if not worker_ids:
        # Nothing matches: no batch, and the AI provider is never called.
        raise NoAvailableApplicationsError(
            "No new, unanalyzed applications match these filters."
        )

    # Cap to available count if user requested more than available
    selected_count = len(worker_ids)

    # Create the batch
    batch = batch_crud.create_batch(
        db,
        owner_id=current_user.id,
        worker_ids=worker_ids,
    )

    logger.info(
        "Created auto-analyze batch: batch_id=%s owner_id=%s requested=%d selected=%d "
        "order=%s job_id=%s company_filter=%s position_filter=%s",
        batch.id,
        current_user.id,
        count,
        selected_count,
        order,
        job_id,
        company is not None,
        position is not None,
    )

    return batch


async def analyze_single_worker(
    db: Session,
    worker: Worker,
) -> tuple[bool, str | None]:
    """Analyze a single worker and persist the result.

    This is the shared analysis function used by both manual and batch analysis.

    Args:
        db: Database session.
        worker: The worker to analyze.

    Returns:
        Tuple of (success, error_message).
    """
    try:
        await single_analysis.run_analysis(db, worker)
        return True, None
    except AIServiceError as exc:
        logger.warning(
            "AI analysis failed for worker_id=%s: %s",
            worker.id,
            exc.message,
        )
        return False, exc.message
    except Exception as exc:
        logger.exception(
            "Unexpected error analyzing worker_id=%s",
            worker.id,
        )
        return False, "The analysis could not be completed. Please try again."


async def run_batch_analysis(batch_id: int) -> None:
    """Run the auto-analyze batch in the background.

    This is the main background processing function. It:
    1. Marks the batch as RUNNING
    2. Processes workers one by one
    3. Updates progress after each worker
    4. Handles failures gracefully (continues with next worker)
    5. Marks the batch as COMPLETED when done

    Args:
        batch_id: The ID of the batch to process.
    """
    db = SessionLocal()
    try:
        # Get the batch
        batch = batch_crud.get_batch_by_id(db, batch_id)
        if batch is None:
            logger.warning(
                "Batch analysis skipped: batch_id=%s not found",
                batch_id,
            )
            return

        # Check if batch should be cancelled
        if batch.status == AnalysisBatchStatus.CANCELLED:
            logger.info(
                "Batch analysis skipped: batch_id=%s was cancelled",
                batch_id,
            )
            return

        # Mark as running
        batch_crud.update_batch(
            db,
            batch,
            status=AnalysisBatchStatus.RUNNING,
        )
        started = time.monotonic()
        logger.info(
            "Batch analysis started: batch_id=%s owner_id=%s total=%d",
            batch_id,
            batch.owner_id,
            len(batch.worker_ids),
        )

        # Process each worker
        worker_ids = batch.worker_ids
        for idx, worker_id in enumerate(worker_ids):
            # Get fresh batch state
            db.expire(batch)
            batch = batch_crud.get_batch_by_id(db, batch_id)
            if batch is None:
                return

            # Check for cancellation before each worker
            if batch.status == AnalysisBatchStatus.CANCELLED:
                logger.info(
                    "Batch analysis cancelled at worker %d/%d: batch_id=%s",
                    idx,
                    len(worker_ids),
                    batch_id,
                )
                return

            # Skip applications that were deleted, moved to another owner or
            # analysed/started elsewhere since the batch was created: they are
            # neither failures nor worth a second (paid) AI call.
            worker = db.get(Worker, worker_id)
            if (
                worker is None
                or worker.job.owner_id != batch.owner_id
                or worker.analysis_status not in ELIGIBLE_ANALYSIS_STATUSES
            ):
                logger.info(
                    "Skipping application no longer eligible: worker_id=%s batch_id=%s",
                    worker_id,
                    batch_id,
                )
                batch_crud.update_batch(
                    db,
                    batch,
                    skipped_count=batch.skipped_count + 1,
                    current_index=idx + 1,
                    current_worker_id=None,
                )
                continue

            # Update batch to show current worker
            batch_crud.update_batch(
                db,
                batch,
                current_index=idx,
                current_worker_id=worker_id,
            )

            # Analyze the worker
            logger.info(
                "Analyzing worker %d/%d: worker_id=%s batch_id=%s",
                idx + 1,
                len(worker_ids),
                worker_id,
                batch_id,
            )

            success, error = await analyze_single_worker(db, worker)

            if success:
                batch_crud.update_batch(
                    db,
                    batch,
                    successful_count=batch.successful_count + 1,
                    current_index=idx + 1,
                    current_worker_id=None,
                )
                logger.info(
                    "Worker analyzed successfully: worker_id=%s batch_id=%s",
                    worker_id,
                    batch_id,
                )
            else:
                batch_crud.update_batch(
                    db,
                    batch,
                    failed_count=batch.failed_count + 1,
                    current_index=idx + 1,
                    current_worker_id=None,
                )
                logger.warning(
                    "Worker analysis failed: worker_id=%s batch_id=%s error=%s",
                    worker_id,
                    batch_id,
                    error,
                )

            # Small delay to avoid overwhelming the AI provider
            await asyncio.sleep(0.1)

        # Mark batch as completed
        batch_crud.update_batch(
            db,
            batch,
            status=AnalysisBatchStatus.COMPLETED,
            finished_at=True,
            current_worker_id=None,
        )

        logger.info(
            "Batch analysis completed: batch_id=%s total=%d successful=%d failed=%d "
            "skipped=%d duration=%.1fs",
            batch_id,
            len(worker_ids),
            batch.successful_count,
            batch.failed_count,
            batch.skipped_count,
            time.monotonic() - started,
        )

    except Exception:
        logger.exception(
            "Unexpected error in batch analysis: batch_id=%s",
            batch_id,
        )
        try:
            batch_crud.update_batch(
                db,
                batch,
                status=AnalysisBatchStatus.FAILED,
                finished_at=True,
            )
        except Exception:
            pass
    finally:
        db.close()


def get_batch_progress(
    db: Session,
    batch_id: int,
    owner_id: int,
) -> dict[str, Any] | None:
    """Get the current progress of a batch.

    Args:
        db: Database session.
        batch_id: The batch ID.
        owner_id: The owner's ID for authorization.

    Returns:
        Dictionary with batch progress info, or None if not found.
    """
    batch = batch_crud.get_batch(db, batch_id, owner_id)
    if batch is None:
        return None

    return {
        "batch_id": batch.id,
        "status": batch.status.value,
        "total": batch.total,
        "processed": batch.processed,
        "successful": batch.successful_count,
        "failed": batch.failed_count,
        "skipped": batch.skipped_count,
        "remaining": batch.remaining,
        "current_application_id": batch.current_worker_id,
        "created_at": batch.created_at,
        "finished_at": batch.finished_at,
    }


