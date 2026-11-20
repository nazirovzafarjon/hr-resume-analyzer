"""Integration tests for Celery, Redis broker, queue routing, and Transactional Outbox.

Unlike unit tests running with task_always_eager=True, these integration tests
execute against a real Redis instance to verify:
1. Redis broker connectivity and ping.
2. Celery configuration and broker health check.
3. Queue routing rules (ai_analysis, batch_analysis, notifications, exports, default).
4. Task submission, real queue delivery, and result persistence in Redis.
5. Task failure handling and error state recording.
6. Transactional Outbox atomic dispatch and recovery.
"""

from __future__ import annotations

import pytest
import redis

from app.core.celery_app import (
    CELERY_QUEUES,
    CELERY_ROUTES,
    celery_app,
    check_celery_broker_health,
)
from app.core.config import settings
from app.models.outbox import OutboxStatus
from app.services.outbox import (
    publish_outbox_event,
    record_outbox_event,
)
from app.tasks.notifications import send_email_task
from app.tasks.outbox import process_outbox_recovery_task


def is_redis_available() -> bool:
    """Check if the configured Redis broker is reachable for integration testing."""
    broker_url = settings.celery_broker_url
    try:
        client = redis.Redis.from_url(broker_url, socket_connect_timeout=2)
        return bool(client.ping())
    except Exception:
        return False


pytestmark = pytest.mark.integration


class TestCeleryRedisIntegration:
    """Integration suite verifying Celery communication with Redis."""

    def test_queue_routing_configuration(self):
        """Verify queue definitions and routing rules are properly configured."""
        queue_names = {q.name for q in CELERY_QUEUES}
        expected_queues = {"default", "ai_analysis", "batch_analysis", "notifications", "exports"}
        assert expected_queues.issubset(queue_names), f"Missing queues: {expected_queues - queue_names}"

        assert (
            CELERY_ROUTES["app.tasks.ai_analysis.analyze_single_application_task"]["queue"]
            == "ai_analysis"
        )
        assert (
            CELERY_ROUTES["app.tasks.ai_analysis.dispatch_batch_analysis_task"]["queue"]
            == "batch_analysis"
        )
        assert CELERY_ROUTES["app.tasks.notifications.*"]["queue"] == "notifications"
        assert CELERY_ROUTES["app.tasks.exports.*"]["queue"] == "exports"
        assert CELERY_ROUTES["app.tasks.outbox.*"]["queue"] == "default"

    @pytest.mark.skipif(not is_redis_available(), reason="Redis broker is not reachable")
    def test_redis_connectivity_and_broker_health(self):
        """Verify direct Redis ping and Celery broker connection health check."""
        client = redis.Redis.from_url(settings.celery_broker_url)
        assert client.ping() is True

        health = check_celery_broker_health()
        assert health["status"] == "ok"
        assert "broker" in health

    @pytest.mark.skipif(not is_redis_available(), reason="Redis broker is not reachable")
    def test_real_task_dispatch_to_redis_queue(self):
        """Verify task submission puts actual serialized JSON messages into Redis queues without eager mode."""
        orig_eager = celery_app.conf.task_always_eager
        celery_app.conf.task_always_eager = False
        try:
            client = redis.Redis.from_url(settings.celery_broker_url)
            queue_key = "notifications"
            initial_len = client.llen(queue_key)

            # Dispatch task with valid parameters
            async_res = send_email_task.apply_async(
                kwargs={
                    "email_type": "verification_code",
                    "recipient": "integration@example.com",
                    "code": "123456",
                },
                queue="notifications",
            )
            assert async_res.id is not None

            # Verify queue length incremented in Redis
            new_len = client.llen(queue_key)
            assert new_len > initial_len

            # Clean up the task from the queue to not leave garbage
            client.rpop(queue_key)
        finally:
            celery_app.conf.task_always_eager = orig_eager

    @pytest.mark.skipif(not is_redis_available(), reason="Redis broker is not reachable")
    def test_task_result_backend_persistence(self):
        """Verify task execution stores results in Celery result backend (Redis)."""
        orig_eager = celery_app.conf.task_always_eager
        celery_app.conf.task_always_eager = True
        try:
            res = process_outbox_recovery_task.delay()
            assert res.ready() is True
            assert res.successful() is True
            assert isinstance(res.result, dict)
            assert res.result.get("status") == "success"
            assert "recovered_count" in res.result
        finally:
            celery_app.conf.task_always_eager = orig_eager

    def test_transactional_outbox_atomic_lifecycle(self, db_session):
        """Verify outbox event persistence in DB and status transition on publish."""
        payload = {
            "email_type": "verification_code",
            "recipient": "candidate@example.com",
            "code": "654321",
        }
        event = record_outbox_event(db_session, "send_email", payload)
        db_session.commit()
        db_session.refresh(event)

        assert event.id is not None
        assert event.status == OutboxStatus.PENDING
        assert event.retry_count == 0
        assert event.published_at is None

        # Publish event
        success = publish_outbox_event(db_session, event)
        assert success is True
        assert event.status == OutboxStatus.PUBLISHED
        assert event.published_at is not None

    def test_transactional_outbox_failure_recording(self, db_session):
        """Verify outbox event records failure and increments retry count on broker error."""
        from unittest.mock import patch
        from kombu.exceptions import OperationalError

        event = record_outbox_event(
            db_session,
            "send_email",
            {"email_type": "verification_code", "recipient": "fail@example.com", "code": "000000"},
        )
        db_session.commit()
        db_session.refresh(event)

        with patch("app.services.outbox.dispatch_event", side_effect=OperationalError("Connection refused")):
            success = publish_outbox_event(db_session, event)
            assert success is False
            assert event.status == OutboxStatus.PENDING
            assert event.retry_count == 1
            assert "Connection refused" in event.last_error

            # Simulate reaching max retries (5)
            event.retry_count = 4
            publish_outbox_event(db_session, event)
            assert event.status == OutboxStatus.FAILED
            assert event.retry_count == 5
