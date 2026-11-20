"""Celery periodic background tasks for Transactional Outbox recovery.

Scans the ``outbox_events`` table periodically for pending events that were not
published immediately (e.g. during a transient Redis outage or worker restart)
and publishes them to Celery.
"""

from __future__ import annotations

import logging
from typing import Any

from celery import Task

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.services.outbox import process_pending_outbox_events

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="app.tasks.outbox.process_outbox_recovery_task",
    max_retries=1,
    acks_late=True,
)
def process_outbox_recovery_task(self: Task, limit: int = 50) -> dict[str, Any]:
    """Scan and publish pending outbox events that have timed out."""
    logger.info("Executing scheduled outbox recovery scan [task_id=%s]", self.request.id)
    with SessionLocal() as db:
        recovered = process_pending_outbox_events(db, limit=limit)
        logger.info("Outbox recovery scan completed: %d events processed", recovered)
        return {
            "status": "success",
            "recovered_count": recovered,
        }
