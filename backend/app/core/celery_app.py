"""Celery distributed task application configuration.

This module initializes and configures the Celery application instance used across
the Resume Analyzer platform for asynchronous background workloads (AI resume
evaluations, batch processing, transactional notifications, and exports).

Key Architecture and Design Decisions:
1. Separation of Queues:
   Workloads are routed to dedicated queues (ai_analysis, batch_analysis, notifications,
   exports, default) to prevent fast, lightweight tasks (e.g., transactional emails)
   from being starved by long-running LLM inferences.
2. Reliability & Acknowledgments:
   - task_acks_late = True: Tasks are acknowledged ONLY AFTER successful completion.
     If a worker crashes or is OOM-killed during AI analysis, the task is requeued.
   - worker_prefetch_multiplier = 1: Disables greedy task prefetching. Each worker
     process reserves exactly one task at a time, ensuring fair distribution.
   - task_reject_on_worker_lost = True: Worker crashes cause immediate task rejection
     back to Redis for another worker to pick up.
3. Serialization:
   Strictly restricted to JSON. No pickle or arbitrary object serialization is allowed.
4. Multitenancy:
   Tasks receive database primary keys (e.g. application_id, batch_id), never
   raw API keys, passwords, or tenant credentials over Redis.
"""

from __future__ import annotations

import logging
from typing import Any

from celery import Celery
from kombu import Queue

from app.core.config import settings

logger = logging.getLogger(__name__)

# Initialize Celery app
celery_app = Celery("resume_analyzer")

# Define explicit task queues
CELERY_QUEUES: tuple[Queue, ...] = (
    Queue("default", routing_key="default.#"),
    Queue("ai_analysis", routing_key="ai.#"),
    Queue("batch_analysis", routing_key="batch.#"),
    Queue("notifications", routing_key="notify.#"),
    Queue("exports", routing_key="export.#"),
)

# Route tasks to their designated queues based on module or task name
CELERY_ROUTES: dict[str, dict[str, str]] = {
    # Single application AI analysis
    "app.tasks.ai_analysis.analyze_single_application_task": {
        "queue": "ai_analysis",
        "routing_key": "ai.single",
    },
    # Batch application AI analysis (individual items and batch orchestrator)
    "app.tasks.ai_analysis.analyze_batch_item_task": {
        "queue": "batch_analysis",
        "routing_key": "batch.item",
    },
    "app.tasks.ai_analysis.dispatch_batch_analysis_task": {
        "queue": "batch_analysis",
        "routing_key": "batch.dispatch",
    },
    # Transactional notifications (Resend emails, system alerts)
    "app.tasks.notifications.*": {
        "queue": "notifications",
        "routing_key": "notify.#",
    },
    # Document exports (Excel, PDF, Word)
    "app.tasks.exports.*": {
        "queue": "exports",
        "routing_key": "export.#",
    },
    # Transactional Outbox recovery scanner
    "app.tasks.outbox.*": {
        "queue": "default",
        "routing_key": "default.outbox",
    },
}

# Apply configuration
celery_app.conf.update(
    # Broker & Result Backend
    broker_url=settings.celery_broker_url,
    result_backend=settings.celery_result_backend,
    broker_connection_retry_on_startup=True,
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Timezone
    timezone="UTC",
    enable_utc=True,
    # Queues & Routing
    task_default_queue=settings.CELERY_TASK_DEFAULT_QUEUE,
    task_queues=list(CELERY_QUEUES),
    task_routes=CELERY_ROUTES,
    # Worker Execution & Reliability
    task_acks_late=settings.CELERY_TASK_ACKS_LATE,
    worker_prefetch_multiplier=settings.CELERY_WORKER_PREFETCH_MULTIPLIER,
    task_reject_on_worker_lost=settings.CELERY_TASK_REJECT_ON_WORKER_LOST,
    # Timeouts (soft limit triggers SoftTimeLimitExceeded; hard limit kills worker)
    task_soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT,
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
    # Result expiration (1 day)
    result_expires=86400,
    # Tracking
    task_track_started=True,
)

# Auto-discover task modules across known packages
celery_app.autodiscover_tasks([
    "app.tasks.ai_analysis",
    "app.tasks.notifications",
    "app.tasks.exports",
    "app.tasks.outbox",
])

# Periodic Celery Beat Schedule
celery_app.conf.beat_schedule = {
    # Scan for pending outbox events every 30 seconds for guaranteed delivery
    "process-pending-outbox-events-every-30s": {
        "task": "app.tasks.outbox.process_outbox_recovery_task",
        "schedule": 30.0,
        "options": {"queue": "default"},
    },
    # Telegram interview reminders (24h / 1h before); a no-op while the bot is off.
    "send-telegram-interview-reminders-every-5m": {
        "task": "app.tasks.notifications.send_interview_reminders_task",
        "schedule": 300.0,
        "options": {"queue": "notifications"},
    },
}


def check_celery_broker_health() -> dict[str, Any]:
    """Check connectivity to the Celery broker (Redis).

    Returns:
        dict containing 'status' ("ok" | "unhealthy") and optional 'error' message.
    """
    try:
        # Inspect connection using Celery's broker pool
        with celery_app.connection_for_read() as connection:
            connection.connect()
            connected = connection.connected
            return {
                "status": "ok" if connected else "unhealthy",
                "broker": connection.as_uri(include_password=False),
            }
    except Exception as exc:
        logger.warning("Celery broker health check failed: %s", exc)
        return {
            "status": "unhealthy",
            "error": str(exc),
        }
