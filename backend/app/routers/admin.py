"""Admin panel API (``/api/admin``). Superuser only.

Security boundary: the router-level dependency runs ``get_current_superuser``
before every endpoint, so an anonymous request gets 401 and an authenticated
HR user gets 403 regardless of which admin path they call. Frontend route
guards are only a convenience on top of this.

Handlers stay thin: parse and validate query parameters, call a service,
return an explicit response schema. Listings share one pagination contract
(``page`` from 1, ``limit`` up to 100, response ``{items, total, page,
limit}``) and sort only by allowlisted keys.

User mutations (activate, deactivate, promote, demote, delete) are served
by the existing ``/api/users/{id}`` endpoints, which apply the same
safeguards and write audit rows; they are not duplicated here.
"""

from datetime import date, datetime, time, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.crud import audit_log as audit_crud
from app.crud import job as job_crud
from app.crud import user as user_crud
from app.crud.admin import WorkerFilters
from app.dependencies.audit import get_audit_context
from app.dependencies.auth import get_current_superuser
from app.models.interview import InterviewStatus as InterviewSessionStatus
from app.models.user import User
from app.models.worker import ApplicationStatus, HiringStatus, InterviewStatus
from app.schemas import admin as schemas
from app.services.admin import directory as admin_directory
from app.services.admin import stats as admin_stats
from app.services.ai import monitoring as ai_monitoring
from app.services.admin import errors as error_monitor
from app.services import platform_settings as platform_settings_service
from app.services.admin import health as system_health
from app.services.audit import AuditAction, AuditContext, AuditResource

router = APIRouter(dependencies=[Depends(get_current_superuser)])

ADMIN_ONLY = "Superuser only: 401 without a token, 403 for non-admin users."

# Shared query parameters -------------------------------------------------

PageParam = Query(1, ge=1, le=10_000, description="Page number, starting at 1")
LimitParam = Query(25, ge=1, le=schemas.MAX_PAGE_SIZE, description="Rows per page (max 100)")
SearchParam = Query(None, max_length=100, description="Case-insensitive search")
OrderParam = Query("desc", description="Sort direction")


def _date_bounds(date_from: date | None, date_to: date | None) -> dict[str, datetime | None]:
    """Turn inclusive calendar dates into UTC datetime bounds."""
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="date_from must be on or before date_to",
        )
    return {
        "date_from": datetime.combine(date_from, time.min, tzinfo=timezone.utc) if date_from else None,
        "date_to": datetime.combine(date_to, time.max, tzinfo=timezone.utc) if date_to else None,
    }


def _clean(search: str | None) -> str | None:
    """Treat a blank search box like no search."""
    return (search.strip() or None) if search else None


# ---------------------------------------------------------------------------
# Dashboard, analytics, filters
# ---------------------------------------------------------------------------


@router.get(
    "/dashboard",
    response_model=schemas.AdminDashboard,
    summary="Platform KPIs, 30-day trend and recent activity",
    description=ADMIN_ONLY,
)
def get_dashboard(db: Session = Depends(get_db)) -> dict:
    return admin_stats.get_dashboard(db)


@router.get(
    "/analytics",
    response_model=schemas.AdminAnalytics,
    summary="Platform analytics for a period",
    description=f"{ADMIN_ONLY} Series use daily buckets for 7d/30d, weekly for 90d, monthly for 12m.",
)
def get_analytics(
    range_param: Literal["7d", "30d", "90d", "12m"] = Query("30d", alias="range"),
    db: Session = Depends(get_db),
) -> dict:
    return admin_stats.get_analytics(db, range_param)


@router.get(
    "/filters",
    response_model=schemas.FilterOptions,
    summary="Options for the HR owner and company filters",
    description=ADMIN_ONLY,
)
def get_filter_options(db: Session = Depends(get_db)) -> schemas.FilterOptions:
    return admin_directory.filter_options(db)


# ---------------------------------------------------------------------------
# Users (read views; mutations live in /api/users)
# ---------------------------------------------------------------------------


@router.get(
    "/users",
    response_model=schemas.Page[schemas.AdminUserRow],
    summary="List users with their job and application counts",
    description=ADMIN_ONLY,
)
def list_users(
    q: str | None = SearchParam,
    status_filter: Literal["active", "inactive"] | None = Query(None, alias="status"),
    role: Literal["admin", "hr"] | None = Query(None),
    date_from: date | None = Query(None, description="Joined on or after (YYYY-MM-DD)"),
    date_to: date | None = Query(None, description="Joined on or before (YYYY-MM-DD)"),
    sort: Literal["name", "email", "created_at", "last_login_at", "jobs", "applications"] = Query(
        "created_at"
    ),
    order: Literal["asc", "desc"] = OrderParam,
    page: int = PageParam,
    limit: int = LimitParam,
    db: Session = Depends(get_db),
) -> schemas.Page[schemas.AdminUserRow]:
    return admin_directory.list_users(
        db,
        page=page,
        limit=limit,
        search=_clean(q),
        is_active=None if status_filter is None else status_filter == "active",
        is_superuser=None if role is None else role == "admin",
        sort=sort,
        order=order,
        **_date_bounds(date_from, date_to),
    )


@router.get(
    "/users/{user_id}",
    response_model=schemas.AdminUserDetail,
    summary="User profile, activity statistics and recent items",
    description=ADMIN_ONLY,
)
def get_user(user_id: int, db: Session = Depends(get_db)) -> schemas.AdminUserDetail:
    user = user_crud.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return admin_directory.get_user_detail(db, user)


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------


@router.get(
    "/jobs",
    response_model=schemas.Page[schemas.AdminJobRow],
    summary="List every job on the platform",
    description=ADMIN_ONLY,
)
def list_jobs(
    q: str | None = SearchParam,
    owner_id: int | None = Query(None, ge=1),
    company: str | None = Query(None, max_length=255),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    sort: Literal["created_at", "position", "company", "applications"] = Query("created_at"),
    order: Literal["asc", "desc"] = OrderParam,
    page: int = PageParam,
    limit: int = LimitParam,
    db: Session = Depends(get_db),
) -> schemas.Page[schemas.AdminJobRow]:
    return admin_directory.list_jobs(
        db,
        page=page,
        limit=limit,
        search=_clean(q),
        owner_id=owner_id,
        company=company or None,
        sort=sort,
        order=order,
        **_date_bounds(date_from, date_to),
    )


@router.get(
    "/jobs/{job_id}",
    response_model=schemas.AdminJobDetail,
    summary="Job details with application status breakdown",
    description=ADMIN_ONLY,
)
def get_job(job_id: int, db: Session = Depends(get_db)) -> schemas.AdminJobDetail:
    detail = admin_directory.get_job_detail(db, job_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return detail


@router.delete(
    "/jobs/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete any job (moderation)",
    description=f"{ADMIN_ONLY} Removes the job and its applications; audited as DELETE_JOB.",
)
def delete_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_superuser),
    audit_ctx: AuditContext = Depends(get_audit_context),
) -> None:
    job = job_crud.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    admin_directory.delete_job(db, current_admin, job, audit_ctx)


# ---------------------------------------------------------------------------
# Applications / candidates
# ---------------------------------------------------------------------------


def _worker_filters(
    q: str | None = SearchParam,
    owner_id: int | None = Query(None, ge=1),
    company: str | None = Query(None, max_length=255),
    job_id: int | None = Query(None, ge=1),
    analysis: Literal["analyzed", "not_analyzed", "analyzing", "failed"] | None = Query(None),
    application_status: ApplicationStatus | None = Query(None),
    hiring_status: HiringStatus | None = Query(None),
    interview_status: InterviewStatus | None = Query(None),
    score_min: float | None = Query(None, ge=0, le=100),
    score_max: float | None = Query(None, ge=0, le=100),
    date_from: date | None = Query(None, description="Submitted on or after"),
    date_to: date | None = Query(None, description="Submitted on or before"),
) -> WorkerFilters:
    if score_min is not None and score_max is not None and score_min > score_max:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="score_min must not exceed score_max",
        )
    return WorkerFilters(
        search=_clean(q),
        owner_id=owner_id,
        company=company or None,
        job_id=job_id,
        analysis=analysis,
        application_status=application_status,
        hiring_status=hiring_status,
        interview_status=interview_status,
        score_min=score_min,
        score_max=score_max,
        **_date_bounds(date_from, date_to),
    )


WorkerSort = Literal["submitted_at", "candidate_at", "name", "ai_score"]


@router.get(
    "/applications",
    response_model=schemas.AdminWorkerPage,
    summary="List every application on the platform",
    description=ADMIN_ONLY,
)
def list_applications(
    filters: WorkerFilters = Depends(_worker_filters),
    sort: WorkerSort = Query("submitted_at"),
    order: Literal["asc", "desc"] = OrderParam,
    page: int = PageParam,
    limit: int = LimitParam,
    db: Session = Depends(get_db),
) -> schemas.AdminWorkerPage:
    return admin_directory.list_workers(db, filters, page=page, limit=limit, sort=sort, order=order)


@router.get(
    "/candidates",
    response_model=schemas.AdminWorkerPage,
    summary="List applications that were moved into the hiring pipeline",
    description=ADMIN_ONLY,
)
def list_candidates(
    filters: WorkerFilters = Depends(_worker_filters),
    sort: WorkerSort = Query("candidate_at"),
    order: Literal["asc", "desc"] = OrderParam,
    page: int = PageParam,
    limit: int = LimitParam,
    db: Session = Depends(get_db),
) -> schemas.AdminWorkerPage:
    filters.candidates_only = True
    return admin_directory.list_workers(db, filters, page=page, limit=limit, sort=sort, order=order)


@router.get(
    "/applications/{worker_id}",
    response_model=schemas.AdminWorkerDetail,
    summary="Application / candidate details, including the stored AI analysis",
    description=f"{ADMIN_ONLY} Read-only; the resume file itself is not served to admins.",
)
def get_application(worker_id: int, db: Session = Depends(get_db)) -> schemas.AdminWorkerDetail:
    detail = admin_directory.get_worker_detail(db, worker_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return detail


# ---------------------------------------------------------------------------
# Interviews
# ---------------------------------------------------------------------------


@router.get(
    "/interviews",
    response_model=schemas.AdminInterviewPage,
    summary="List every scheduled interview",
    description=ADMIN_ONLY,
)
def list_interviews(
    q: str | None = SearchParam,
    owner_id: int | None = Query(None, ge=1, description="HR user who scheduled it"),
    company: str | None = Query(None, max_length=255),
    job_id: int | None = Query(None, ge=1),
    status_filter: InterviewSessionStatus | None = Query(None, alias="status"),
    date_from: date | None = Query(None, description="Scheduled on or after"),
    date_to: date | None = Query(None, description="Scheduled on or before"),
    sort: Literal["scheduled_at", "created_at"] = Query("scheduled_at"),
    order: Literal["asc", "desc"] = OrderParam,
    page: int = PageParam,
    limit: int = LimitParam,
    db: Session = Depends(get_db),
) -> schemas.AdminInterviewPage:
    return admin_directory.list_interviews(
        db,
        page=page,
        limit=limit,
        search=_clean(q),
        owner_id=owner_id,
        company=company or None,
        job_id=job_id,
        status=status_filter,
        sort=sort,
        order=order,
        **_date_bounds(date_from, date_to),
    )


# ---------------------------------------------------------------------------
# AI monitoring
# ---------------------------------------------------------------------------


@router.get(
    "/ai-analysis",
    response_model=schemas.AIOverview,
    summary="AI analysis health, volume and failures",
    description=ADMIN_ONLY,
)
def get_ai_overview(db: Session = Depends(get_db)) -> dict:
    return ai_monitoring.overview(db)


@router.get(
    "/ai-analysis/runs",
    response_model=schemas.Page[schemas.AIRunRow],
    summary="Recorded AI provider attempts",
    description=f"{ADMIN_ONLY} Contains no prompts, resume text or credentials.",
)
def list_ai_runs(
    status_filter: Literal["completed", "failed"] | None = Query(None, alias="status"),
    kind: Literal["application", "vacancy"] | None = Query(None),
    error_category: str | None = Query(None, max_length=32),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    page: int = PageParam,
    limit: int = LimitParam,
    db: Session = Depends(get_db),
) -> dict:
    if error_category and error_category not in ai_monitoring.ERROR_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown error category"
        )
    return ai_monitoring.list_runs(
        db,
        page=page,
        limit=limit,
        status=status_filter,
        kind=kind,
        error_category=error_category,
        **_date_bounds(date_from, date_to),
    )


# ---------------------------------------------------------------------------
# Audit logs + system errors
# ---------------------------------------------------------------------------


@router.get(
    "/audit-logs/meta",
    response_model=schemas.AuditMeta,
    summary="Known audit actions and resource types (for filters)",
    description=ADMIN_ONLY,
)
def get_audit_meta() -> schemas.AuditMeta:
    return schemas.AuditMeta(actions=AuditAction.all(), resource_types=AuditResource.all())


@router.get(
    "/audit-logs",
    response_model=schemas.Page[schemas.AuditLogEntry],
    summary="Search the audit trail",
    description=f"{ADMIN_ONLY} Read-only: the audit trail cannot be edited or deleted through the API.",
)
def list_audit_logs(
    q: str | None = SearchParam,
    actor_id: int | None = Query(None, ge=1),
    action: str | None = Query(None, max_length=64),
    resource_type: str | None = Query(None, max_length=32),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    page: int = PageParam,
    limit: int = LimitParam,
    db: Session = Depends(get_db),
) -> schemas.Page[schemas.AuditLogEntry]:
    entries, total = audit_crud.list_entries(
        db,
        page=page,
        limit=limit,
        search=_clean(q),
        actor_user_id=actor_id,
        action=action or None,
        resource_type=resource_type or None,
        **_date_bounds(date_from, date_to),
    )
    return schemas.Page[schemas.AuditLogEntry](
        items=[schemas.AuditLogEntry.model_validate(entry) for entry in entries],
        total=total,
        page=page,
        limit=limit,
    )


@router.get(
    "/system-errors",
    response_model=schemas.SystemErrorPage,
    summary="Server errors (5xx) recorded by the API",
    description=f"{ADMIN_ONLY} No request bodies or stack traces are stored.",
)
def list_system_errors(
    q: str | None = SearchParam,
    status_code: int | None = Query(None, ge=500, le=599),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    page: int = PageParam,
    limit: int = LimitParam,
    db: Session = Depends(get_db),
) -> dict:
    return error_monitor.list_errors(
        db,
        page=page,
        limit=limit,
        search=_clean(q),
        status_code=status_code,
        **_date_bounds(date_from, date_to),
    )


# ---------------------------------------------------------------------------
# Settings + health
# ---------------------------------------------------------------------------


def _settings_response(db: Session) -> schemas.AdminSettings:
    row = platform_settings_service.get_settings(db)
    updated_by = user_crud.get_user_by_id(db, row.updated_by_id) if row.updated_by_id else None
    return schemas.AdminSettings(
        runtime=schemas.RuntimeSettings(
            registration_enabled=row.registration_enabled,
            updated_at=row.updated_at,
            updated_by_email=updated_by.email if updated_by else None,
        ),
        configuration=platform_settings_service.configuration_overview(db),
    )


@router.get(
    "/settings",
    response_model=schemas.AdminSettings,
    summary="Runtime switches and configuration status",
    description=f"{ADMIN_ONLY} Secrets are never returned; configuration shows presence only.",
)
def get_settings(db: Session = Depends(get_db)) -> schemas.AdminSettings:
    return _settings_response(db)


@router.patch(
    "/settings",
    response_model=schemas.AdminSettings,
    summary="Change runtime switches",
    description=f"{ADMIN_ONLY} Only runtime switches are editable; changes are audited.",
)
def update_settings(
    payload: schemas.RuntimeSettingsUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_superuser),
    audit_ctx: AuditContext = Depends(get_audit_context),
) -> schemas.AdminSettings:
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    platform_settings_service.update_settings(db, current_admin, changes, audit_ctx)
    return _settings_response(db)


@router.get(
    "/system-health",
    response_model=schemas.HealthReport,
    summary="Health of the API, database, AI provider, email, storage and workers",
    description=f"{ADMIN_ONLY} Lightweight checks only; no paid AI calls, no emails sent.",
)
def get_system_health(db: Session = Depends(get_db)) -> dict:
    return system_health.get_report(db)
