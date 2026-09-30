"""Health checks for the admin "System Health" page.

Every check is cheap and side-effect free:

* **Database** — one ``SELECT 1`` round trip, timed.
* **AI provider** — configuration presence plus the failure rate of recent
  recorded attempts. No provider request is made: a probe would spend
  tokens/quota on every page load.
* **Email** — configuration presence only (probing would send mail).
* **Storage** — the upload directory exists, is writable, and has free space.
* **Background workers** — auto-analyze batches and single analyses that
  are stuck past their expected lifetime.

A check that throws is reported as a component status, never as a 500, and
details are fixed, safe sentences: no DSNs, hostnames, keys or exception text.
"""

import logging
import os
import shutil
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.crud import ai_analysis_run as run_crud
from app.models.analysis_batch import AnalysisBatch, AnalysisBatchStatus
from app.models.application import AnalysisStatus, Application
from app.services.application_analysis import STALE_ANALYSIS_SECONDS

logger = logging.getLogger(__name__)

_PROCESS_STARTED = time.monotonic()

#: Share of failed AI attempts in the last hour that marks the provider degraded
#: (only once there are enough attempts for the rate to mean something).
_AI_FAILURE_RATE_DEGRADED = 0.5
_AI_MIN_SAMPLE = 5
#: Free disk share below which storage is reported as degraded.
_MIN_FREE_DISK_RATIO = 0.10
#: A batch still queued/running after this long is considered stuck.
_STUCK_BATCH_AFTER = timedelta(hours=2)


def _component(key: str, status: str, detail: str = "", latency_ms: float | None = None, **metrics: Any):
    return {"key": key, "status": status, "detail": detail, "latency_ms": latency_ms, "metrics": metrics}


def _ping_database(db: Session) -> None:
    db.execute(text("SELECT 1"))


def check_api() -> dict[str, Any]:
    return _component(
        "api",
        "healthy",
        "The API is serving requests.",
        uptime_seconds=int(time.monotonic() - _PROCESS_STARTED),
        debug_mode=settings.DEBUG,
    )


def check_database(db: Session) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        _ping_database(db)
    except Exception:  # noqa: BLE001 -- any driver/network error means "down"
        logger.exception("Health check: database ping failed")
        db.rollback()
        return _component("database", "down", "The database did not respond.")
    latency = round((time.perf_counter() - started) * 1000, 1)
    return _component("database", "healthy", "Connected.", latency_ms=latency)


def check_ai_provider(db: Session) -> dict[str, Any]:
    cfg = settings.ai_provider_config()
    recent = run_crud.outcome_summary(db, datetime.now(timezone.utc) - timedelta(hours=1))
    metrics = {
        "provider": cfg["provider"],
        "model": cfg["model"] or None,
        "attempts_1h": recent["total"],
        "failed_1h": recent["failed"],
    }
    if not cfg["api_key"] or not cfg["model"]:
        return _component(
            "ai_provider",
            "not_configured",
            "No platform API key or model is configured; only users with their own key can run analyses.",
            **metrics,
        )
    if recent["total"] >= _AI_MIN_SAMPLE and recent["failed"] / recent["total"] >= _AI_FAILURE_RATE_DEGRADED:
        return _component(
            "ai_provider", "degraded", "Most AI attempts in the last hour failed.", **metrics
        )
    if recent["completed"] == 0:
        # Configuration alone proves nothing about the provider being up.
        return _component(
            "ai_provider",
            "configured",
            "Configured, but no successful attempt in the last hour to confirm it works.",
            **metrics,
        )
    return _component(
        "ai_provider",
        "healthy",
        "Recent AI attempts succeeded. The provider is never called by this check.",
        **metrics,
    )


def check_email() -> dict[str, Any]:
    if not settings.RESEND_API_KEY:
        return _component(
            "email",
            "not_configured",
            "No email API key: password-reset links are written to the server log.",
            provider="resend",
        )
    return _component(
        "email",
        "configured",
        "Configured. Not probed, to avoid sending mail.",
        provider="resend",
        sandbox_sender=settings.EMAIL_FROM == "onboarding@resend.dev",
    )


def check_storage() -> dict[str, Any]:
    upload_dir = Path(settings.UPLOAD_DIR)
    if not upload_dir.is_dir() or not os.access(upload_dir, os.W_OK):
        return _component("storage", "down", "The upload directory is missing or not writable.")
    usage = shutil.disk_usage(upload_dir)
    free_ratio = usage.free / usage.total if usage.total else 0
    metrics = {"free_gb": round(usage.free / 1024**3, 1), "free_percent": round(free_ratio * 100, 1)}
    if free_ratio < _MIN_FREE_DISK_RATIO:
        return _component("storage", "degraded", "Disk space for uploads is running low.", **metrics)
    return _component("storage", "healthy", "Upload directory is writable.", **metrics)


def check_workers(db: Session) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    active = (AnalysisBatchStatus.QUEUED, AnalysisBatchStatus.RUNNING)
    running, stuck = db.execute(
        select(
            func.count(AnalysisBatch.id),
            func.count(AnalysisBatch.id).filter(AnalysisBatch.created_at < now - _STUCK_BATCH_AFTER),
        ).where(AnalysisBatch.status.in_(active))
    ).one()
    stale_analyses = db.execute(
        select(func.count(Application.id)).where(
            Application.analysis_status == AnalysisStatus.ANALYZING,
            Application.analysis_started_at < now - timedelta(seconds=STALE_ANALYSIS_SECONDS),
        )
    ).scalar_one()
    metrics = {
        "active_batches": int(running),
        "stuck_batches": int(stuck),
        "stale_analyses": int(stale_analyses),
    }
    if stuck or stale_analyses:
        # Typically a restart interrupted in-process background work; HR can
        # retry stale analyses, and stuck batches can be cancelled.
        return _component(
            "workers", "degraded", "Some background analyses appear to be stuck.", **metrics
        )
    return _component("workers", "healthy", "Background analysis is running normally.", **metrics)


def _safe(key: str, check: Callable[[], dict[str, Any]], db: Session) -> dict[str, Any]:
    """Run a check; an unexpected failure becomes a "degraded" component."""
    try:
        return check()
    except Exception:  # noqa: BLE001
        logger.exception("Health check %s failed", key)
        db.rollback()
        return _component(key, "degraded", "This check could not be completed.")


def get_report(db: Session) -> dict[str, Any]:
    database = check_database(db)
    database_up = database["status"] != "down"

    components = [
        check_api(),
        database,
        _safe("ai_provider", lambda: check_ai_provider(db), db)
        if database_up
        else _component("ai_provider", "degraded", "Unavailable while the database is down."),
        check_email(),
        _safe("storage", check_storage, db),
        _safe("workers", lambda: check_workers(db), db)
        if database_up
        else _component("workers", "degraded", "Unavailable while the database is down."),
    ]
    statuses = {component["status"] for component in components}
    overall = "down" if not database_up else "degraded" if statuses & {"degraded", "down"} else "healthy"
    return {"status": overall, "checked_at": datetime.now(timezone.utc), "components": components}
