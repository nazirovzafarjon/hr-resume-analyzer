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
import logging
from typing import Any

from celery import Task
from kombu.exceptions import OperationalError

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.application import AnalysisStatus, Application
from app.services import application_analysis as single_analysis
from app.services.ai import provider as ai_provider_service
from app.services.ai.job_analyzer import AIServiceError

logger = logging.getLogger(__name__)

# Transient HTTP status codes from AI providers that warrant a Celery-level retry
_RETRYABLE_STATUS_CODES = {429, 502, 503, 504}


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
) -> dict[str, Any]:
    """Execute AI analysis for a single candidate application.

    Args:
        self: Bound Celery task instance for retry orchestration.
        application_id: Primary key of the Application to analyze.
        force: If True, re-analyzes even if a completed analysis already exists.
        actor_id: Optional User ID of the recruiter/admin who triggered the analysis.

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
        if single_analysis._is_run_active(application):
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
                single_analysis.run_analysis(db, application, force=force)
            )
            return {
                "status": "completed",
                "application_id": application_id,
                "score": analyzed_application.ai_score,
                "analysis_status": analyzed_application.analysis_status.value,
            }

        except ai_provider_service.AIConfigurationRequiredError as exc:
            # Permanent configuration error: the recruiter has not connected an AI provider.
            # Do NOT retry. The application remains in its current state.
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
            # Check if this error is transient and retryable
            status_code = getattr(exc, "status_code", 500)
            if status_code in _RETRYABLE_STATUS_CODES and self.request.retries < self.max_retries:
                retry_delay = 5 * (2 ** self.request.retries)  # Exponential backoff: 5s, 10s
                logger.warning(
                    "Task encountered transient AI error (HTTP %s). Retrying in %ss (attempt %d/%d): %s",
                    status_code,
                    retry_delay,
                    self.request.retries + 1,
                    self.max_retries,
                    exc.message,
                )
                raise self.retry(exc=exc, countdown=retry_delay)

            # Permanent or non-retryable error (e.g., 400, 401, 403, 422, or retries exhausted).
            # single_analysis.run_analysis has already marked the application FAILED and recorded diagnostics.
            logger.error(
                "Task failed permanently: application_id=%s status=%s error=%s",
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

        except Exception as exc:
            logger.exception(
                "Unexpected failure in analyze_single_application_task: application_id=%s",
                application_id,
            )
            return {
                "status": "unexpected_error",
                "application_id": application_id,
                "error": str(exc),
            }
