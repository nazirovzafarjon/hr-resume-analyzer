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
from app.crud import application as application_crud
from app.models.analysis_batch import AnalysisBatch, AnalysisBatchStatus
from app.models.application import AnalysisStatus, Application, ApplicationStatus
from app.models.job import Job
from app.models.user import User
from app.services import application_analysis as single_analysis
from app.services.ai import provider as ai_provider_service
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
        Application.application_status == ApplicationStatus.NEW,
        Application.analysis_status.in_(ELIGIBLE_ANALYSIS_STATUSES),
    ]
    if job_id is not None:
        conditions.append(Application.job_id == job_id)
    if company is not None:
        conditions.append(Job.company_name == company)
    if position is not None:
        conditions.append(Job.position == position)
    return conditions


def _get_eligible_application_ids(
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
        limit: Maximum number of application IDs to return (None for unlimited).
        job_id / company / position: Optional filters (``None`` = all).
    """
    query = (
        select(Application.id)
        .join(Application.job)
        .where(*_eligible_filter(owner_id, job_id=job_id, company=company, position=position))
    )

    # Ordering: created_at ASC/DESC, then id for determinism
    if order == "newest":
        query = query.order_by(Application.created_at.desc(), Application.id.desc())
    else:  # oldest (default)
        query = query.order_by(Application.created_at.asc(), Application.id.asc())

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
        select(func.count(Application.id))
        .join(Application.job)
        .where(*_eligible_filter(owner_id, job_id=job_id, company=company, position=position))
    )
    return db.execute(query).scalar_one()


def get_filter_options(db: Session, owner_id: int) -> list[dict[str, Any]]:
    """Company/position pairs that currently have eligible applications.

    Feeds the Company and Position dropdowns, with the number of eligible
    applications per pair, so HR only sees choices that can select something.
    """
    query = (
        select(Job.company_name, Job.position, func.count(Application.id))
        .join(Application.job)
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

    # Get eligible application IDs
    application_ids = _get_eligible_application_ids(
        db,
        current_user.id,
        order=order,
        limit=count,
        job_id=job_id,
        company=company,
        position=position,
    )

    if not application_ids:
        # Nothing matches: no batch, and the AI provider is never called.
        raise NoAvailableApplicationsError(
            "No new, unanalyzed applications match these filters."
        )

    # Cap to available count if user requested more than available
    selected_count = len(application_ids)

    # Create the batch
    batch = batch_crud.create_batch(
        db,
        owner_id=current_user.id,
        application_ids=application_ids,
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


async def analyze_single_application(
    db: Session,
    application: Application,
) -> tuple[bool, str | None]:
    """Analyze a single application and persist the result.

    This is the shared analysis function used by both manual and batch analysis.

    Args:
        db: Database session.
        application: The application to analyze.

    Returns:
        Tuple of (success, error_message).
    """
    try:
        await single_analysis.run_analysis(db, application)
        return True, None
    except ai_provider_service.AIConfigurationRequiredError:
        # Not about this application: the whole batch cannot run.
        raise
    except AIServiceError as exc:
        logger.warning(
            "AI analysis failed for application_id=%s: %s",
            application.id,
            exc.message,
        )
        return False, exc.message
    except Exception as exc:
        logger.exception(
            "Unexpected error analyzing application_id=%s",
            application.id,
        )
        return False, "The analysis could not be completed. Please try again."


async def run_batch_analysis(batch_id: int) -> None:
    """Run the auto-analyze batch in the background.

    This is the main background processing function. It:
    1. Marks the batch as RUNNING
    2. Processes applications one by one
    3. Updates progress after each application
    4. Handles failures gracefully (continues with next application)
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
            len(batch.application_ids),
        )

        # Process each application
        application_ids = batch.application_ids
        for idx, application_id in enumerate(application_ids):
            # Get fresh batch state
            db.expire(batch)
            batch = batch_crud.get_batch_by_id(db, batch_id)
            if batch is None:
                return

            # Check for cancellation before each application
            if batch.status == AnalysisBatchStatus.CANCELLED:
                logger.info(
                    "Batch analysis cancelled at application %d/%d: batch_id=%s",
                    idx,
                    len(application_ids),
                    batch_id,
                )
                return

            # Skip applications that were deleted, moved to another owner or
            # analysed/started elsewhere since the batch was created: they are
            # neither failures nor worth a second (paid) AI call.
            application = db.get(Application, application_id)
            if (
                application is None
                or application.job.owner_id != batch.owner_id
                or application.analysis_status not in ELIGIBLE_ANALYSIS_STATUSES
            ):
                logger.info(
                    "Skipping application no longer eligible: application_id=%s batch_id=%s",
                    application_id,
                    batch_id,
                )
                batch_crud.update_batch(
                    db,
                    batch,
                    skipped_count=batch.skipped_count + 1,
                    current_index=idx + 1,
                    current_application_id=None,
                )
                continue

            # Update batch to show current application
            batch_crud.update_batch(
                db,
                batch,
                current_index=idx,
                current_application_id=application_id,
            )

            # Analyze the application
            logger.info(
                "Analyzing application %d/%d: application_id=%s batch_id=%s",
                idx + 1,
                len(application_ids),
                application_id,
                batch_id,
            )

            try:
                success, error = await analyze_single_application(db, application)
            except ai_provider_service.AIConfigurationRequiredError:
                # The owner removed their AI configuration mid-batch (it is
                # resolved per application at run time). Stop instead of
                # failing every remaining application; they stay "new".
                logger.warning(
                    "Batch analysis stopped, AI configuration removed: batch_id=%s at %d/%d",
                    batch_id,
                    idx,
                    len(application_ids),
                )
                batch_crud.update_batch(
                    db,
                    batch,
                    status=AnalysisBatchStatus.FAILED,
                    finished_at=True,
                    current_application_id=None,
                )
                return

            if success:
                batch_crud.update_batch(
                    db,
                    batch,
                    successful_count=batch.successful_count + 1,
                    current_index=idx + 1,
                    current_application_id=None,
                )
                logger.info(
                    "Application analyzed successfully: application_id=%s batch_id=%s",
                    application_id,
                    batch_id,
                )
            else:
                batch_crud.update_batch(
                    db,
                    batch,
                    failed_count=batch.failed_count + 1,
                    current_index=idx + 1,
                    current_application_id=None,
                )
                logger.warning(
                    "Application analysis failed: application_id=%s batch_id=%s error=%s",
                    application_id,
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
            current_application_id=None,
        )

        logger.info(
            "Batch analysis completed: batch_id=%s total=%d successful=%d failed=%d "
            "skipped=%d duration=%.1fs",
            batch_id,
            len(application_ids),
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
        "current_application_id": batch.current_application_id,
        "created_at": batch.created_at,
        "finished_at": batch.finished_at,
    }


