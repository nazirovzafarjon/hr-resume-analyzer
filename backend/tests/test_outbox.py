"""Tests for Transactional Outbox pattern and background recovery."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import pytest

from app.models.outbox import OutboxEvent, OutboxStatus
from app.services.outbox import (
    process_pending_outbox_events,
    publish_outbox_event,
    record_and_dispatch,
    record_outbox_event,
)


def test_record_and_publish_outbox_event_success(db_session):
    """Test standard outbox recording and immediate dispatch."""
    payload = {"application_id": 1, "force": False, "actor_id": 42}

    with patch("app.tasks.ai_analysis.analyze_single_application_task.delay") as mock_delay:
        event = record_and_dispatch(
            db_session,
            event_type="analyze_single_application",
            payload=payload,
        )

        assert mock_delay.call_count == 1
        mock_delay.assert_called_once_with(application_id=1, force=False, actor_id=42)

    db_session.refresh(event)
    assert event.status == OutboxStatus.PUBLISHED
    assert event.published_at is not None
    assert event.retry_count == 0


def test_outbox_dispatch_failure_and_recovery(db_session):
    """Test outbox recovery scanner picks up un-dispatched pending events."""
    payload = {"batch_id": 99}

    # 1. Simulate initial failure during dispatch (e.g. Redis unavailable)
    with patch(
        "app.tasks.ai_analysis.dispatch_batch_analysis_task.delay",
        side_effect=ConnectionError("Redis broker offline"),
    ):
        event = record_outbox_event(db_session, "dispatch_batch_analysis", payload)
        db_session.commit()
        db_session.refresh(event)

        success = publish_outbox_event(db_session, event)
        assert success is False

    db_session.refresh(event)
    assert event.status == OutboxStatus.PENDING
    assert event.retry_count == 1
    assert "Redis broker offline" in event.last_error

    # 2. Simulate time passing so the event passes the 10-second recovery threshold
    event.created_at = datetime.now(timezone.utc) - timedelta(seconds=20)
    db_session.commit()

    # 3. Recovery scanner runs with healthy broker
    with patch("app.tasks.ai_analysis.dispatch_batch_analysis_task.delay") as mock_delay:
        recovered = process_pending_outbox_events(db_session)
        assert recovered == 1
        mock_delay.assert_called_once_with(batch_id=99)

    db_session.refresh(event)
    assert event.status == OutboxStatus.PUBLISHED


def test_outbox_max_retries_marked_failed(db_session):
    """Test outbox events exceeding max retries are marked FAILED."""
    event = record_outbox_event(db_session, "send_email", {"recipient": "bad@example.com"})
    event.retry_count = 4  # Next failure will hit retry threshold 5
    db_session.commit()

    with patch(
        "app.tasks.notifications.send_email_task.delay",
        side_effect=ConnectionError("Permanent connection error"),
    ):
        success = publish_outbox_event(db_session, event)
        assert success is False

    db_session.refresh(event)
    assert event.status == OutboxStatus.FAILED
    assert event.retry_count == 5
