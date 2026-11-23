"""Celery background tasks for AI resume analysis.

This module provides distributed task execution for:
- Single application resume analysis (analyze_single_application_task)
- Batch application analysis items (analyze_batch_item_task)
- Batch orchestration and dispatching (dispatch_batch_analysis_task)

Architecture & Reliability Principles:
1. Thin Task Orchestration:
   Celery tasks do not reimplement AI analysis, prompts, or scoring. They orchestrate
   execution and delegate all business logic to ``app.services.application_analysis``
   and ``app.services.ai.*``.
2. Isolated Database Sessions:
   Every task opens and closes its own SQLAlchemy database session using
   ``with SessionLocal() as db:``. Sessions are never shared across tasks or threads.
3. Multi-Tenant Security:
   Tasks receive only database IDs (e.g., application_id, batch_id). Credentials and
   API keys are resolved and decrypted from PostgreSQL inside the worker process;
   no secrets or raw resumes are passed over the Redis broker.
4. Idempotency & Bounded Retries:
   Tasks check the application's current database state before executing. If analysis
   is already completed (and force=False), the task safely returns early.
   Only transient network or rate-limit errors (HTTP 429, 502, 503, 504) trigger Celery
   retries with exponential backoff (max 2 retries, capped to avoid multiplying the
   internal HTTP client's 3-attempt budget). Permanent configuration or input errors
   (400, 401, 403, 422) fail fast without retrying.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from datetime import datetime, timezone
import logging
from typing import Any

from celery import Task
from kombu.exceptions import OperationalError
from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.crud import batch as batch_crud
from app.models.analysis_batch import AnalysisBatch, AnalysisBatchStatus
from app.models.analysis_batch_item import AnalysisBatchItem, BatchItemStatus
from app.models.application import AnalysisStatus, Application
from app.services import application_analysis as single_analysis
from app.services.ai import provider as ai_provider_service
from app.services.ai.batch import ELIGIBLE_ANALYSIS_STATUSES
from app.services.ai.job_analyzer import AIServiceError

logger = logging.getLogger(__name__)

# Note on AI provider retries:
# Upstream HTTP calls to AI providers are already automatically retried with exponential
# backoff inside `app.services.ai.job_analyzer` (up to settings.AI_MAX_RETRIES = 3).
# Therefore, any AIServiceError that surfaces here has already exhausted its retries.
# Retrying AIServiceError in Celery would multiply attempts (3 * 3 = 9), violate rate
# limits, and produce duplicate audit runs. Celery-level retries are reserved strictly
# for broker/transport connectivity errors (OperationalError, ConnectionError, TimeoutError).


def _utcnow() -> datetime:
    """Return the current UTC wall-clock time (timezone-aware)."""
    return datetime.now(timezone.utc)


def _run_async(coro: Any) -> Any:
    """Execute an asynchronous coroutine from a synchronous Celery task worker.

    Safely handles both standard Celery prefork worker processes (where no event loop
    is active) and async environments (e.g., test runners with an active event loop).
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    else:
        if loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)


@celery_app.task(
    bind=True,
    name="app.tasks.ai_analysis.analyze_single_application_task",
    max_retries=2,
    default_retry_delay=5,
    acks_late=True,
)
def analyze_single_application_task(
    self: Task,
    application_id: int,
    force: bool = False,
    actor_id: int | None = None,
    claimed_at: str | None = None,
) -> dict[str, Any]:
    """Execute AI analysis for a single candidate application.

    Args:
        self: Bound Celery task instance for retry orchestration.
        application_id: Primary key of the Application to analyze.
        force: If True, re-analyzes even if a completed analysis already exists.
        actor_id: Optional User ID of the recruiter/admin who triggered the analysis.
        claimed_at: Claim token set by the API when it marked the run as
            in flight before queuing it (see ``claim_run``).

    Returns:
        A dict summary containing task outcome, application_id, status, and score.
    """
    logger.info(
        "Celery task started: analyze_single_application_task[id=%s, app_id=%s, force=%s, actor=%s]",
        self.request.id,
        application_id,
        force,
        actor_id,
    )

    with SessionLocal() as db:
        application = db.get(Application, application_id)
        if application is None:
            logger.warning(
                "Task aborting: Application %s not found in database", application_id
            )
            return {"status": "not_found", "application_id": application_id}

        # 1. Idempotency guard: Skip if already completed unless force=True
        if (
            not force
            and application.analysis_status == AnalysisStatus.COMPLETED
            and application.ai_analysis_details
        ):
            logger.info(
                "Task idempotency: Application %s already analysed; skipping",
                application_id,
            )
            return {
                "status": "already_completed",
                "application_id": application_id,
                "score": application.ai_score,
            }

        # 2. Concurrency guard: If another worker is actively analyzing and not stale, skip
        claimed = single_analysis.owns_claim(application, claimed_at)
        if single_analysis._is_run_active(application) and not claimed:
            logger.info(
                "Task skipped: Application %s is currently being analyzed by another run",
                application_id,
            )
            return {
                "status": "in_progress",
                "application_id": application_id,
            }

        # 3. Execute analysis via the application_analysis business service
        try:
            analyzed_application = _run_async(
                single_analysis.run_analysis(
                    db, application, force=force, claimed_at=claimed_at if claimed else None
                )
            )
            return {
                "status": "completed",
                "application_id": application_id,
                "score": analyzed_application.ai_score,
                "analysis_status": analyzed_application.analysis_status.value,
            }

        except ai_provider_service.AIConfigurationRequiredError as exc:
            # Permanent configuration error: the recruiter has not connected an AI provider.
            # Do NOT retry. An unclaimed run leaves the application as it was;
            # a claimed one must not stay "analyzing", so it is marked failed.
            if claimed:
                single_analysis._mark_failed(db, application, exc.message)
            logger.warning(
                "Task failed permanently (AI provider not configured): application_id=%s: %s",
                application_id,
                exc.message,
            )
            return {
                "status": "configuration_required",
                "application_id": application_id,
                "error": exc.message,
            }

        except AIServiceError as exc:
            # AIServiceError (e.g. 400, 401, 403, 429, 502, 503) has already completed all
            # internal retries in the AI layer. single_analysis.run_analysis has already marked
            # the application FAILED and recorded diagnostics in PostgreSQL.
            status_code = getattr(exc, "status_code", 500)
            logger.error(
                "Task failed: application_id=%s status=%s error=%s",
                application_id,
                status_code,
                exc.message,
            )
            return {
                "status": "failed",
                "application_id": application_id,
                "error": exc.message,
                "status_code": status_code,
            }

        except (OperationalError, ConnectionError, TimeoutError) as exc:
            # Network or broker disconnects during task execution
            if self.request.retries < self.max_retries:
                retry_delay = 5 * (2 ** self.request.retries)
                logger.warning(
                    "Task connection error. Retrying in %ss (attempt %d/%d): %s",
                    retry_delay,
                    self.request.retries + 1,
                    self.max_retries,
                    exc,
                )
                raise self.retry(exc=exc, countdown=retry_delay)
            raise

        except Exception:
            logger.exception(
                "Unexpected failure in analyze_single_application_task: application_id=%s",
                application_id,
            )
            raise


@celery_app.task(
    bind=True,
    name="app.tasks.ai_analysis.dispatch_batch_analysis_task",
    acks_late=True,
)
def dispatch_batch_analysis_task(self: Task, batch_id: int) -> dict[str, Any]:
    """Orchestrate and dispatch execution of an auto-analyze batch.

    Transitions batch from QUEUED to RUNNING, verifies state, and enqueues
    individual analyze_batch_item_task jobs for all items in the batch.
    """
    logger.info("Dispatching batch analysis: batch_id=%s [task_id=%s]", batch_id, self.request.id)

    with SessionLocal() as db:
        batch = db.get(AnalysisBatch, batch_id)
        if batch is None:
            logger.warning("Dispatch aborted: Batch %s not found", batch_id)
            return {"status": "batch_not_found", "batch_id": batch_id}

        if batch.status == AnalysisBatchStatus.CANCELLED:
            logger.info("Dispatch aborted: Batch %s was cancelled", batch_id)
            return {"status": "cancelled", "batch_id": batch_id}

        # Transition to RUNNING
        batch.status = AnalysisBatchStatus.RUNNING
        db.commit()

        # Query all items in this batch ordered by primary key
        items = (
            db.execute(
                select(AnalysisBatchItem)
                .where(AnalysisBatchItem.batch_id == batch_id)
                .order_by(AnalysisBatchItem.id)
            )
            .scalars()
            .all()
        )

        logger.info(
            "Batch %s has %d items to process. Dispatching tasks to batch_analysis queue...",
            batch_id,
            len(items),
        )

        for item in items:
            analyze_batch_item_task.delay(
                batch_id=batch_id,
                item_id=item.id,
                application_id=item.application_id,
            )

        return {
            "status": "dispatched",
            "batch_id": batch_id,
            "total_items": len(items),
        }


@celery_app.task(
    bind=True,
    name="app.tasks.ai_analysis.analyze_batch_item_task",
    max_retries=2,
    default_retry_delay=5,
    acks_late=True,
)
def analyze_batch_item_task(
    self: Task,
    batch_id: int,
    item_id: int,
    application_id: int,
) -> dict[str, Any]:
    """Process an individual application item within an auto-analyze batch."""
    logger.info(
        "Processing batch item: batch_id=%s item_id=%s app_id=%s [task_id=%s]",
        batch_id,
        item_id,
        application_id,
        self.request.id,
    )

    with SessionLocal() as db:
        batch = db.get(AnalysisBatch, batch_id)
        if batch is None:
            return {"status": "batch_not_found"}

        # Check cooperative cancellation before starting work
        if batch.status == AnalysisBatchStatus.CANCELLED:
            item = db.get(AnalysisBatchItem, item_id)
            if item and item.status != BatchItemStatus.CANCELLED:
                batch_crud.update_batch_item(db, item, status=BatchItemStatus.CANCELLED)
            return {"status": "cancelled", "item_id": item_id}

        item = db.get(AnalysisBatchItem, item_id)
        if item is None:
            return {"status": "item_not_found"}

        if item.status == BatchItemStatus.COMPLETED:
            return {"status": "already_completed", "item_id": item_id}

        # Mark item as RUNNING
        batch_crud.update_batch_item(
            db,
            item,
            status=BatchItemStatus.RUNNING,
            celery_task_id=self.request.id,
            started_at=_utcnow(),
        )
        batch_crud.increment_batch_counter(
            db, batch_id, current_application_id=application_id
        )

        # Verify application eligibility
        application = db.get(Application, application_id)
        is_eligible = (
            application is not None
            and (batch.owner.is_superuser or application.job.owner_id == batch.owner_id)
            and application.analysis_status in ELIGIBLE_ANALYSIS_STATUSES
        )

        if not is_eligible:
            logger.info(
                "Batch item no longer eligible: batch_id=%s app_id=%s",
                batch_id,
                application_id,
            )
            batch_crud.update_batch_item(
                db, item, status=BatchItemStatus.SKIPPED, completed_at=_utcnow()
            )
            batch_crud.increment_batch_counter(db, batch_id, skipped=True)
            batch_crud.check_and_complete_batch(db, batch_id)
            return {"status": "skipped", "application_id": application_id}

        # Run AI analysis
        try:
            _run_async(single_analysis.run_analysis(db, application))
            batch_crud.update_batch_item(
                db, item, status=BatchItemStatus.COMPLETED, completed_at=_utcnow()
            )
            batch_crud.increment_batch_counter(db, batch_id, successful=True)
            batch_crud.check_and_complete_batch(db, batch_id)
            return {"status": "completed", "application_id": application_id}

        except ai_provider_service.AIConfigurationRequiredError as exc:
            if application.job.owner_id != batch.owner_id:
                # Admin batch: skip applications where the job owner has no AI setup
                batch_crud.update_batch_item(
                    db,
                    item,
                    status=BatchItemStatus.SKIPPED,
                    error_message=exc.message,
                    completed_at=_utcnow(),
                )
                batch_crud.increment_batch_counter(db, batch_id, skipped=True)
                batch_crud.check_and_complete_batch(db, batch_id)
                return {"status": "skipped", "application_id": application_id}

            # Recruiter removed AI setup mid-batch: fail this item and fail batch
            batch_crud.update_batch_item(
                db,
                item,
                status=BatchItemStatus.FAILED,
                error_message=exc.message,
                completed_at=_utcnow(),
            )
            batch_crud.increment_batch_counter(db, batch_id, failed=True)
            batch_crud.update_batch(
                db, batch, status=AnalysisBatchStatus.FAILED, finished_at=True
            )
            return {"status": "failed", "application_id": application_id, "error": exc.message}

        except AIServiceError as exc:
            batch_crud.update_batch_item(
                db,
                item,
                status=BatchItemStatus.FAILED,
                error_message=exc.message,
                completed_at=_utcnow(),
            )
            batch_crud.increment_batch_counter(db, batch_id, failed=True)
            batch_crud.check_and_complete_batch(db, batch_id)
            return {"status": "failed", "application_id": application_id, "error": exc.message}

        except (OperationalError, ConnectionError, TimeoutError) as exc:
            if self.request.retries < self.max_retries:
                retry_delay = 5 * (2 ** self.request.retries)
                raise self.retry(exc=exc, countdown=retry_delay)
            batch_crud.update_batch_item(
                db,
                item,
                status=BatchItemStatus.FAILED,
                error_message=str(exc),
                completed_at=_utcnow(),
            )
            batch_crud.increment_batch_counter(db, batch_id, failed=True)
            batch_crud.check_and_complete_batch(db, batch_id)
            return {"status": "failed", "application_id": application_id, "error": str(exc)}

        except Exception as exc:
            logger.exception("Unexpected error processing batch item: item_id=%s", item_id)
            batch_crud.update_batch_item(
                db,
                item,
                status=BatchItemStatus.FAILED,
                error_message=str(exc),
                completed_at=_utcnow(),
            )
            batch_crud.increment_batch_counter(db, batch_id, failed=True)
            batch_crud.check_and_complete_batch(db, batch_id)
            return {"status": "failed", "application_id": application_id, "error": str(exc)}
