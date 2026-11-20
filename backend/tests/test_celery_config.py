"""Unit and integration tests for Celery app and Redis configuration."""

import pytest
from app.core.celery_app import celery_app, check_celery_broker_health
from app.core.config import settings
from app.core.redis import check_redis_health, get_redis_client


def test_celery_app_initialization():
    """Verify Celery app has correct configuration flags and queue topology."""
    assert celery_app.main == "resume_analyzer"
    conf = celery_app.conf

    # Serialization
    assert conf.task_serializer == "json"
    assert conf.result_serializer == "json"
    assert "json" in conf.accept_content

    # Reliability settings
    assert conf.task_acks_late is True
    assert conf.worker_prefetch_multiplier == 1
    assert conf.task_reject_on_worker_lost is True
    assert conf.task_default_queue == "default"

    # Queues
    queue_names = {q.name for q in conf.task_queues}
    expected_queues = {"default", "ai_analysis", "batch_analysis", "notifications", "exports"}
    assert expected_queues.issubset(queue_names)

    # Routes
    assert conf.task_routes["app.tasks.ai_analysis.analyze_single_application_task"]["queue"] == "ai_analysis"
    assert conf.task_routes["app.tasks.ai_analysis.analyze_batch_item_task"]["queue"] == "batch_analysis"
    assert conf.task_routes["app.tasks.ai_analysis.dispatch_batch_analysis_task"]["queue"] == "batch_analysis"
    assert conf.task_routes["app.tasks.notifications.*"]["queue"] == "notifications"
    assert conf.task_routes["app.tasks.exports.*"]["queue"] == "exports"


def test_redis_connection_and_health():
    """Verify direct Redis ping returns healthy status and reasonable latency."""
    health = check_redis_health()
    assert health["status"] == "ok"
    assert "latency_ms" in health
    assert health["latency_ms"] >= 0


def test_celery_broker_health_check():
    """Verify Celery broker connectivity helper."""
    broker_health = check_celery_broker_health()
    assert broker_health["status"] == "ok"
    assert "redis://" in broker_health["broker"]
