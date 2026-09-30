"""Platform-wide aggregates for the admin Dashboard and Analytics pages.

Unlike ``dashboard_analytics`` (one HR user's data), everything here spans the
whole platform. All counting happens in PostgreSQL: time series are bucketed
with ``date_trunc`` on UTC timestamps and distributions use ``GROUP BY``, so
no page ever pulls raw rows into Python to count them.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal

from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from app.crud import audit_log as audit_crud
from app.crud import system_error as system_error_crud
from app.models.ai_analysis_run import AIAnalysisRun
from app.models.interview import Interview
from app.models.job import Job
from app.models.user import User
from app.models.application import AnalysisStatus, ApplicationStatus, HiringStatus, InterviewStatus, Application
from app.services.audit import AuditAction
from app.services.dashboard_analytics import SCORE_BUCKETS

AdminRange = Literal["7d", "30d", "90d", "12m"]
Bucket = Literal["day", "week", "month"]

#: Range -> (bucket size, number of buckets).
_RANGES: dict[str, tuple[Bucket, int]] = {
    "7d": ("day", 7),
    "30d": ("day", 30),
    "90d": ("week", 13),
    "12m": ("month", 12),
}

#: Sign-ins and sign-outs dominate the trail by volume; the dashboard's
#: "recent activity" shows platform events instead.
_ACTIVITY_NOISE = (AuditAction.LOGIN, AuditAction.LOGOUT)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Time buckets
# ---------------------------------------------------------------------------


def _floor(day: date, bucket: Bucket) -> date:
    if bucket == "week":
        return day - timedelta(days=day.weekday())  # ISO week starts Monday
    if bucket == "month":
        return day.replace(day=1)
    return day


def _bucket_keys(bucket: Bucket, count: int, today: date) -> list[date]:
    """The last ``count`` bucket start dates, oldest first, ending today."""
    keys = [_floor(today, bucket)]
    while len(keys) < count:
        current = keys[0]
        if bucket == "month":
            previous = (current - timedelta(days=1)).replace(day=1)
        elif bucket == "week":
            previous = current - timedelta(weeks=1)
        else:
            previous = current - timedelta(days=1)
        keys.insert(0, previous)
    return keys


def _counts_by_bucket(
    db: Session, column: Any, bucket: Bucket, since: datetime, *conditions: Any
) -> dict[date, int]:
    """COUNT(*) per ``date_trunc(bucket)`` of ``column`` (in UTC), since a moment."""
    # timezone('UTC', timestamptz) yields the UTC wall-clock time, so buckets
    # do not shift with the database session's TimeZone setting.
    bucket_expr = func.date_trunc(bucket, func.timezone("UTC", column)).label("bucket")
    rows = db.execute(
        select(bucket_expr, func.count())
        .where(column >= since, *conditions)
        .group_by(bucket_expr)
    ).all()
    return {row[0].date(): int(row[1]) for row in rows}


def build_series(db: Session, range_: AdminRange) -> tuple[Bucket, list[dict[str, Any]], datetime]:
    """Per-bucket counts of new users, jobs, applications, interviews and AI runs.

    Returns ``(bucket, points, period_start)``; every bucket in the range is
    present (zero-filled) so charts have a continuous x-axis.
    """
    bucket, count = _RANGES[range_]
    keys = _bucket_keys(bucket, count, _utcnow().date())
    since = datetime.combine(keys[0], datetime.min.time(), tzinfo=timezone.utc)

    metrics = {
        "registrations": _counts_by_bucket(db, User.created_at, bucket, since),
        "jobs": _counts_by_bucket(db, Job.created_at, bucket, since),
        "applications": _counts_by_bucket(db, Application.created_at, bucket, since),
        "interviews": _counts_by_bucket(db, Interview.created_at, bucket, since),
        "ai_completed": _counts_by_bucket(
            db, AIAnalysisRun.created_at, bucket, since, AIAnalysisRun.status == "completed"
        ),
        "ai_failed": _counts_by_bucket(
            db, AIAnalysisRun.created_at, bucket, since, AIAnalysisRun.status == "failed"
        ),
    }
    points = [
        {"date": key.isoformat(), **{name: values.get(key, 0) for name, values in metrics.items()}}
        for key in keys
    ]
    return bucket, points, since


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


def user_totals(db: Session) -> dict[str, int]:
    total, active, admins = db.execute(
        select(
            func.count(User.id),
            func.count(User.id).filter(User.is_active.is_(True)),
            func.count(User.id).filter(User.is_superuser.is_(True)),
        )
    ).one()
    return {
        "total": int(total),
        "active": int(active),
        "inactive": int(total) - int(active),
        "admins": int(admins),
    }


def get_dashboard(db: Session) -> dict[str, Any]:
    """KPIs, a 30-day trend and the latest platform events."""
    users = user_totals(db)
    applications, candidates, analyzed, failed = db.execute(
        select(
            func.count(Application.id),
            func.count(Application.id).filter(Application.candidate_at.is_not(None)),
            func.count(Application.id).filter(Application.analysis_status == AnalysisStatus.COMPLETED),
            func.count(Application.id).filter(Application.analysis_status == AnalysisStatus.FAILED),
        )
    ).one()
    jobs = db.execute(select(func.count(Job.id))).scalar_one()
    interviews = db.execute(select(func.count(Interview.id))).scalar_one()
    errors_24h = system_error_crud.count_since(db, _utcnow() - timedelta(hours=24))

    _, trend, _ = build_series(db, "30d")
    activity = audit_crud.recent_entries(db, 12, exclude_actions=_ACTIVITY_NOISE)

    return {
        "kpis": {
            "users_total": users["total"],
            "users_active": users["active"],
            "users_inactive": users["inactive"],
            "admins": users["admins"],
            "jobs": int(jobs),
            "applications": int(applications),
            "candidates": int(candidates),
            "interviews": int(interviews),
            "ai_analyzed": int(analyzed),
            "ai_failed": int(failed),
            "errors_24h": errors_24h,
        },
        "trend": trend,
        "recent_activity": activity,
    }


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


def _distribution(db: Session, column: Any, enum_cls: Any, since: datetime) -> list[dict[str, Any]]:
    """Counts for every value of ``enum_cls`` among applications since ``since``."""
    rows = db.execute(
        select(column, func.count(Application.id)).where(Application.created_at >= since).group_by(column)
    ).all()
    counts = {value.value: int(count) for value, count in rows}
    return [{"key": member.value, "count": counts.get(member.value, 0)} for member in enum_cls]


def _score_distribution(db: Session, since: datetime) -> list[dict[str, Any]]:
    # Half-open buckets [low, next_low) so fractional scores (e.g. 49.5) are
    # never dropped between two buckets; the top bucket includes 100.
    lows = [low for _, low, _ in SCORE_BUCKETS]
    whens = []
    for index, (label, low, _high) in enumerate(SCORE_BUCKETS):
        upper = lows[index + 1] if index + 1 < len(lows) else None
        condition = (
            Application.ai_score >= low
            if upper is None
            else and_(Application.ai_score >= low, Application.ai_score < upper)
        )
        whens.append((condition, label))
    bucket_expr = case(*whens, else_=None).label("bucket")
    rows = db.execute(
        select(bucket_expr, func.count(Application.id))
        .where(Application.analysis_status == AnalysisStatus.COMPLETED, Application.created_at >= since)
        .group_by(bucket_expr)
    ).all()
    counts = {label: int(count) for label, count in rows if label is not None}
    return [{"key": label, "count": counts.get(label, 0)} for label, _, _ in SCORE_BUCKETS]


def get_analytics(db: Session, range_: AdminRange) -> dict[str, Any]:
    """Platform analytics for the selected period.

    Series, totals, distributions and rankings cover records created inside
    the period; user totals and applications-per-job are all-time figures.
    """
    bucket, series, since = build_series(db, range_)
    totals = {
        key: sum(point[key] for point in series)
        for key in ("registrations", "jobs", "applications", "interviews", "ai_completed", "ai_failed")
    }

    company_rows = db.execute(
        select(
            Job.company_name,
            func.count(func.distinct(Job.id)),
            func.count(Application.id).filter(Application.created_at >= since),
        )
        .outerjoin(Application, Application.job_id == Job.id)
        .where(Job.created_at >= since)
        .group_by(Job.company_name)
        .order_by(func.count(func.distinct(Job.id)).desc(), Job.company_name)
        .limit(8)
    ).all()

    top_job_rows = db.execute(
        select(Job.id, Job.position, Job.company_name, User.email, func.count(Application.id))
        .join(Application, Application.job_id == Job.id)
        .join(User, User.id == Job.owner_id)
        .where(Application.created_at >= since)
        .group_by(Job.id, Job.position, Job.company_name, User.email)
        .order_by(func.count(Application.id).desc(), Job.id)
        .limit(8)
    ).all()

    all_jobs = db.execute(select(func.count(Job.id))).scalar_one()
    all_applications = db.execute(select(func.count(Application.id))).scalar_one()
    avg_score = db.execute(
        select(func.avg(Application.ai_score)).where(
            Application.analysis_status == AnalysisStatus.COMPLETED, Application.created_at >= since
        )
    ).scalar()

    return {
        "range": range_,
        "bucket": bucket,
        "series": series,
        "totals": totals,
        "users": user_totals(db),
        "application_status": _distribution(db, Application.application_status, ApplicationStatus, since),
        "analysis_status": _distribution(db, Application.analysis_status, AnalysisStatus, since),
        "hiring_status": _distribution(db, Application.hiring_status, HiringStatus, since),
        "interview_status": _distribution(db, Application.interview_status, InterviewStatus, since),
        "score_distribution": _score_distribution(db, since),
        "top_companies": [
            {"company": company, "jobs": int(jobs), "applications": int(apps)}
            for company, jobs, apps in company_rows
        ],
        "top_jobs": [
            {
                "job_id": job_id,
                "position": position,
                "company_name": company,
                "owner_email": email,
                "applications": int(count),
            }
            for job_id, position, company, email, count in top_job_rows
        ],
        "avg_applications_per_job": round(all_applications / all_jobs, 1) if all_jobs else 0.0,
        "avg_ai_score": round(float(avg_score), 1) if avg_score is not None else None,
    }
