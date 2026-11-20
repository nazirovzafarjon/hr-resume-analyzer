"""Transactional Outbox service for reliable at-least-once message delivery.

Prevents dual-write state corruption between PostgreSQL and Redis by persisting
events inside the database transaction before publishing them to Celery.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from typing import Any

from kombu.exceptions import KombuError, OperationalError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.outbox import OutboxEvent, OutboxStatus
from app.tasks.ai_analysis import (
    analyze_single_application_task,
    dispatch_batch_analysis_task,
)
from app.tasks.exports import generate_export_task
from app.tasks.notifications import send_email_task

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    """Return the current UTC wall-clock time (timezone-aware)."""
    return datetime.now(timezone.utc)


def record_outbox_event(
    db: Session,
    event_type: str,
    payload: dict[str, Any],
) -> OutboxEvent:
    """Record an event in the outbox table within the caller's database transaction."""
    event = OutboxEvent(
        event_type=event_type,
        payload=payload,
        status=OutboxStatus.PENDING,
    )
    db.add(event)
    return event


def dispatch_event(event: OutboxEvent) -> None:
    """Route and dispatch an outbox event to its designated Celery task."""
    event_type = event.event_type
    payload = event.payload

    if event_type == "analyze_single_application":
        analyze_single_application_task.delay(**payload)
    elif event_type == "dispatch_batch_analysis":
        dispatch_batch_analysis_task.delay(**payload)
    elif event_type == "send_email":
        send_email_task.delay(**payload)
    elif event_type == "generate_export":
        generate_export_task.delay(**payload)
    else:
        raise ValueError(f"Unknown outbox event_type: {event_type}")


def publish_outbox_event(db: Session, event: OutboxEvent) -> bool:
    """Dispatch an outbox event to Celery and update its status in PostgreSQL."""
    try:
        dispatch_event(event)
        event.status = OutboxStatus.PUBLISHED
        event.published_at = _utcnow()
        db.commit()
        return True
    except (KombuError, OperationalError, ConnectionError, TimeoutError, OSError) as exc:
        logger.warning(
            "Failed to publish outbox event id=%s type=%s: %s",
            event.id,
            event.event_type,
            exc,
        )
        event.retry_count += 1
        event.last_error = str(exc)[:1000]
        if event.retry_count >= 5:
            event.status = OutboxStatus.FAILED
        db.commit()
        return False


def record_and_dispatch(
    db: Session,
    event_type: str,
    payload: dict[str, Any],
) -> OutboxEvent:
    """Record an outbox event, commit the transaction, and dispatch to Celery."""
    event = record_outbox_event(db, event_type, payload)
    db.commit()
    db.refresh(event)

    publish_outbox_event(db, event)
    return event


def process_pending_outbox_events(db: Session, limit: int = 50) -> int:
    """Background recovery scanner to publish any unhandled pending outbox events.

    Picks events older than 10 seconds (to avoid racing fresh commits).
    """
    threshold = _utcnow() - timedelta(seconds=10)
    query = (
        select(OutboxEvent)
        .where(
            OutboxEvent.status == OutboxStatus.PENDING,
            OutboxEvent.created_at <= threshold,
        )
        .order_by(OutboxEvent.id.asc())
        .limit(limit)
    )
    events = list(db.execute(query).scalars().all())

    published_count = 0
    for event in events:
        if publish_outbox_event(db, event):
            published_count += 1

    return published_count
