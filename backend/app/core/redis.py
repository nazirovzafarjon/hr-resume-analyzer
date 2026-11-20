"""Redis client utilities and health monitoring.

Provides connection pooling and health check helpers for Redis, which serves
as the Celery message broker and can be used for caching or temporary lock storage.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import redis
from app.core.config import settings

logger = logging.getLogger(__name__)

# Module-level connection pool cache
_redis_client: redis.Redis | None = None


def get_redis_client() -> redis.Redis:
    """Return a shared Redis client instance backed by a connection pool."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_timeout=5.0,
            socket_connect_timeout=5.0,
        )
    return _redis_client


def check_redis_health() -> dict[str, Any]:
    """Ping Redis to verify availability and latency.

    Returns:
        dict containing 'status', 'latency_ms', and optional 'error'.
    """
    start = time.perf_counter()
    try:
        client = get_redis_client()
        pong = client.ping()
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        if pong:
            return {
                "status": "ok",
                "latency_ms": latency_ms,
            }
        return {
            "status": "unhealthy",
            "error": "Redis PING returned non-truthy response",
            "latency_ms": latency_ms,
        }
    except Exception as exc:
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.warning("Redis health check failed: %s", exc)
        return {
            "status": "unhealthy",
            "error": str(exc),
            "latency_ms": latency_ms,
        }
