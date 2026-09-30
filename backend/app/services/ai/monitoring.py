"""Record AI provider attempts for the admin AI monitoring page.

The analysis services call :func:`record_run` once per provider attempt.
Like auditing, recording is best effort: a monitoring failure is logged and
never changes the outcome the HR user sees.

Only safe diagnostics are stored: provider, model id, key source
("default" platform key / "custom" user key), a normalized error category,
the API status we reported and the *user-facing* error message, which the
analyzers already keep free of provider payloads and credentials.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.crud import ai_analysis_run as run_crud
from app.models.ai_analysis_run import AIAnalysisRun
from app.models.ai_provider_config import UserAIProviderConfig
from app.models.user import User
from app.models.analysis_batch import AnalysisBatch
from app.models.application import AnalysisStatus, Application
from app.services.ai.job_analyzer import (
    AIInvalidResponseError,
    AIProviderAuthError,
    AIProviderUnavailableError,
    AIRateLimitError,
    AIServiceError,
)

logger = logging.getLogger(__name__)

KIND_APPLICATION = "application"
KIND_VACANCY = "vacancy"

STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"

#: Every error category a run can carry (also used for API filter validation).
ERROR_CATEGORIES = (
    "rate_limited",
    "auth",
    "unavailable",
    "invalid_response",
    "bad_request",
    "not_found",
    "validation",
    "unexpected",
)


def categorize(exc: BaseException) -> str:
    """Map an analyzer exception to a stable, display-friendly category."""
    if isinstance(exc, AIRateLimitError):
        return "rate_limited"
    if isinstance(exc, AIProviderAuthError):
        return "auth"
    if isinstance(exc, AIProviderUnavailableError):
        return "unavailable"
    if isinstance(exc, AIInvalidResponseError):
        return "invalid_response"
    if isinstance(exc, AIServiceError):
        code = exc.status_code
        if code == 404:
            return "not_found"
        if code == 422:
            return "validation"
        if code == 400:
            return "bad_request"
        if code == 429:
            return "rate_limited"
        if code in (502, 503, 504):
            # A remapped auth failure for a user's own key (see
            # ai_provider.safe_error_for) arrives as a plain 502.
            return "unavailable"
        return "unexpected"
    return "unexpected"


def record_run(
    db: Session,
    *,
    kind: str,
    cfg: dict[str, Any] | None,
    duration_ms: int | None,
    owner_id: int | None,
    job_id: int | None = None,
    application_id: int | None = None,
    score: float | None = None,
    error: BaseException | None = None,
) -> None:
    """Persist one attempt. ``error=None`` means the attempt succeeded."""
    cfg = cfg or {}
    try:
        run_crud.create_run(
            db,
            kind=kind,
            status=STATUS_FAILED if error is not None else STATUS_COMPLETED,
            owner_id=owner_id,
            job_id=job_id,
            application_id=application_id,
            # cfg may be empty when resolving the provider itself failed.
            provider=(cfg.get("provider") or None),
            model=(str(cfg.get("model") or "")[:200] or None),
            source=cfg.get("source"),
            duration_ms=duration_ms,
            score=score,
            error_category=categorize(error) if error is not None else None,
            http_status=getattr(error, "status_code", 500) if error is not None else None,
            error_message=(
                (getattr(error, "message", None) or "Unexpected error")[:500]
                if error is not None
                else None
            ),
        )
    except Exception:  # noqa: BLE001 -- monitoring must never break analysis
        logger.exception("Could not record AI analysis run: kind=%s", kind)
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------------------
# Admin read views
# ---------------------------------------------------------------------------


def _totals(summary: dict[str, Any]) -> dict[str, Any]:
    finished = summary["completed"] + summary["failed"]
    return {
        **summary,
        "success_rate": round(summary["completed"] / finished * 100, 1) if finished else None,
    }


def overview(db: Session) -> dict[str, Any]:
    """Everything the AI monitoring page shows above the run table."""
    since_24h = datetime.now(timezone.utc) - timedelta(hours=24)
    status_rows = db.execute(
        select(Application.analysis_status, func.count(Application.id)).group_by(Application.analysis_status)
    ).all()
    status_counts = {status.value: int(count) for status, count in status_rows}
    avg_score = db.execute(
        select(func.avg(Application.ai_score)).where(Application.analysis_status == AnalysisStatus.COMPLETED)
    ).scalar()

    batches = db.execute(
        select(AnalysisBatch, User.email)
        .outerjoin(User, User.id == AnalysisBatch.owner_id)
        .order_by(AnalysisBatch.created_at.desc(), AnalysisBatch.id.desc())
        .limit(10)
    ).all()

    platform = settings.ai_provider_config()
    custom_users = db.execute(
        select(func.count(UserAIProviderConfig.id)).where(UserAIProviderConfig.is_active.is_(True))
    ).scalar_one()

    return {
        "runs_all_time": _totals(run_crud.outcome_summary(db)),
        "runs_24h": _totals(run_crud.outcome_summary(db, since_24h)),
        "analysis_status": [
            {"key": status.value, "count": status_counts.get(status.value, 0)}
            for status in AnalysisStatus
        ],
        "avg_score": round(float(avg_score), 1) if avg_score is not None else None,
        "providers": [
            {"key": provider or "unknown", "count": count}
            for provider, count in run_crud.grouped_counts(db, AIAnalysisRun.provider)
        ],
        "failure_categories": [
            {"key": category or "unexpected", "count": count}
            for category, count in run_crud.grouped_counts(
                db, AIAnalysisRun.error_category, status=STATUS_FAILED
            )
        ],
        "recent_batches": [
            {
                "id": batch.id,
                "owner_email": email,
                "status": batch.status.value,
                "total": batch.total,
                "successful": batch.successful_count,
                "failed": batch.failed_count,
                "skipped": batch.skipped_count,
                "created_at": batch.created_at,
                "finished_at": batch.finished_at,
            }
            for batch, email in batches
        ],
        "platform_provider": {
            "provider": platform["provider"],
            "model": platform["model"] or None,
            "api_key_configured": bool(platform["api_key"]),
            "custom_provider_users": int(custom_users),
        },
    }


def list_runs(db: Session, *, page: int, limit: int, **filters: Any) -> dict[str, Any]:
    rows, total = run_crud.list_runs(db, page=page, limit=limit, **filters)
    return {
        "items": [
            {
                "id": run.id,
                "created_at": run.created_at,
                "kind": run.kind,
                "status": run.status,
                "owner_email": owner_email,
                "job_id": run.job_id,
                "position": position,
                "company_name": company,
                "application_id": run.application_id,
                "provider": run.provider,
                "model": run.model,
                "source": run.source,
                "duration_ms": run.duration_ms,
                "score": run.score,
                "error_category": run.error_category,
                "http_status": run.http_status,
                "error_message": run.error_message,
            }
            for run, owner_email, position, company in rows
        ],
        "total": total,
        "page": page,
        "limit": limit,
    }
