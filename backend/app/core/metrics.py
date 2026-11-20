"""Prometheus metrics collector and instrumentor.

Collects system, API, Celery, database connection pool, and business metrics
without high-cardinality labels or personal identifiable information (PII).
"""

from __future__ import annotations

import time
from typing import Callable
from fastapi import Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings

# ------------------------------------------------------------------------------
# Metric Instruments
# ------------------------------------------------------------------------------

# 1. API HTTP Metrics
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total count of HTTP requests processed by endpoint and status",
    ["method", "endpoint", "status_code"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# 2. Database Connection Pool Metrics
DB_POOL_SIZE = Gauge("db_pool_size", "Current configured database connection pool size")
DB_POOL_CHECKED_IN = Gauge("db_pool_checked_in", "Database connections currently idle in pool")
DB_POOL_CHECKED_OUT = Gauge("db_pool_checked_out", "Database connections currently in use")
DB_POOL_OVERFLOW = Gauge("db_pool_overflow", "Database overflow connections currently active")

# 3. Celery Background Processing Metrics
CELERY_TASK_EVENTS_TOTAL = Counter(
    "celery_task_events_total",
    "Total count of Celery tasks processed by name and terminal status",
    ["task_name", "status"],
)

CELERY_TASK_DURATION_SECONDS = Histogram(
    "celery_task_duration_seconds",
    "Duration of Celery background task execution in seconds",
    ["task_name"],
    buckets=(0.1, 0.5, 1.0, 5.0, 15.0, 30.0, 60.0, 120.0, 300.0),
)

# 4. Business & AI Operations Metrics
RESUME_ANALYSES_TOTAL = Counter(
    "resume_analyses_total",
    "Total count of single resume analyses executed",
    ["status"],
)

BATCH_ANALYSES_TOTAL = Counter(
    "batch_analyses_total",
    "Total count of batch resume analysis jobs processed",
    ["status"],
)

AI_PROVIDER_REQUESTS_TOTAL = Counter(
    "ai_provider_requests_total",
    "Total count of outbound requests made to external AI providers",
    ["provider", "status"],
)

AI_PROVIDER_LATENCY_SECONDS = Histogram(
    "ai_provider_latency_seconds",
    "Outbound AI provider request latency in seconds",
    ["provider"],
    buckets=(0.5, 1.0, 2.5, 5.0, 10.0, 20.0, 30.0, 60.0),
)


# ------------------------------------------------------------------------------
# Helpers & Middleware
# ------------------------------------------------------------------------------

def _normalize_path(path: str) -> str:
    """Group variable path parameters into generic route templates to avoid metric cardinality explosion."""
    parts = path.strip("/").split("/")
    normalized = []
    for part in parts:
        # Check if part is numeric ID or UUID hex
        if part.isdigit():
            normalized.append("{id}")
        elif len(part) in (32, 36) and all(c in "0123456789abcdef-ABCDEF" for c in part):
            normalized.append("{uuid}")
        else:
            normalized.append(part)
    return "/" + "/".join(normalized) if normalized else "/"


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Measures request count and duration per route."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not settings.PROMETHEUS_METRICS_ENABLED or request.url.path in ("/metrics", "/health", "/health/liveness"):
            return await call_next(request)

        start_time = time.perf_counter()
        method = request.method
        route = request.scope.get("root_path", "") + request.url.path
        endpoint = _normalize_path(route)

        try:
            response = await call_next(request)
            status_code = str(response.status_code)
        except Exception:
            status_code = "500"
            raise
        finally:
            duration = time.perf_counter() - start_time
            HTTP_REQUESTS_TOTAL.labels(
                method=method, endpoint=endpoint, status_code=status_code
            ).inc()
            HTTP_REQUEST_DURATION_SECONDS.labels(
                method=method, endpoint=endpoint
            ).observe(duration)

        return response


def update_db_pool_metrics(engine) -> None:
    """Read connection pool counters from SQLAlchemy engine and update Prometheus gauges."""
    try:
        pool = engine.pool
        if hasattr(pool, "size"):
            DB_POOL_SIZE.set(pool.size())
            DB_POOL_CHECKED_IN.set(pool.checkedin())
            DB_POOL_CHECKED_OUT.set(pool.checkedout())
            DB_POOL_OVERFLOW.set(pool.overflow())
    except Exception:
        pass


def metrics_endpoint_response() -> Response:
    """Generate Prometheus exposition text response."""
    from app.core.database import engine
    update_db_pool_metrics(engine)
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)
