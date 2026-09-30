"""Dashboard analytics aggregation for the `/dashboard/analytics` endpoint.

Pure reporting: reads Job/Worker/Interview rows scoped to the requesting HR
user and produces the shapes the Dashboard and Analytics pages render. Never
writes, and never touches application/AI/interview business rules.
"""

from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models.interview import Interview
from app.models.job import Job
from app.models.worker import AnalysisStatus, ApplicationStatus, Worker

AnalyticsRange = Literal["7d", "30d", "90d"]

_RANGE_DAYS: dict[AnalyticsRange, int] = {"7d": 7, "30d": 30, "90d": 90}

#: AI score buckets (label, low, high), shared with the admin analytics.
SCORE_BUCKETS = [
    ("0-49", 0, 49),
    ("50-59", 50, 59),
    ("60-69", 60, 69),
    ("70-79", 70, 79),
    ("80-89", 80, 89),
    ("90-100", 90, 100),
]


def _as_utc(dt: datetime) -> datetime:
    """Normalize a (possibly naive) datetime to UTC-aware."""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _floor_to_bucket(dt: datetime, weekly: bool) -> date:
    """Bucket key for a timestamp: the day, or the Monday of its ISO week."""
    day = _as_utc(dt).date()
    return day - timedelta(days=day.weekday()) if weekly else day


def get_analytics(db: Session, owner_id: int, range_: AnalyticsRange = "30d") -> dict:
    """Return comprehensive, real-data hiring analytics for one HR user."""
    now = datetime.now(timezone.utc)
    days = _RANGE_DAYS[range_]
    weekly = range_ == "90d"
    period_start = now - timedelta(days=days)
    previous_start = period_start - timedelta(days=days)

    # --- Trend: applications + interviews per bucket, in one query each ---
    app_times = [
        row[0]
        for row in db.query(Worker.created_at)
        .join(Worker.job)
        .filter(Job.owner_id == owner_id, Worker.created_at >= period_start)
        .all()
    ]
    interview_times = [
        row[0]
        for row in db.query(Interview.created_at)
        .filter(Interview.hr_id == owner_id, Interview.created_at >= period_start)
        .all()
    ]
    apps_by_bucket = Counter(_floor_to_bucket(t, weekly) for t in app_times)
    interviews_by_bucket = Counter(_floor_to_bucket(t, weekly) for t in interview_times)

    step = timedelta(weeks=1) if weekly else timedelta(days=1)
    cursor = _floor_to_bucket(period_start, weekly)
    end_bucket = _floor_to_bucket(now, weekly)
    trend = []
    while cursor <= end_bucket:
        trend.append(
            {
                "date": cursor.isoformat(),
                "applications": apps_by_bucket.get(cursor, 0),
                "interviews": interviews_by_bucket.get(cursor, 0),
            }
        )
        cursor += step

    # --- Previous period totals, for a genuine (non-fabricated) %-delta ---
    prev_applications = (
        db.query(func.count(Worker.id))
        .join(Worker.job)
        .filter(
            Job.owner_id == owner_id,
            Worker.created_at >= previous_start,
            Worker.created_at < period_start,
        )
        .scalar()
        or 0
    )
    prev_interviews = (
        db.query(func.count(Interview.id))
        .filter(
            Interview.hr_id == owner_id,
            Interview.created_at >= previous_start,
            Interview.created_at < period_start,
        )
        .scalar()
        or 0
    )

    # --- Status distribution: every real ApplicationStatus value ---
    status_rows = (
        db.query(Worker.application_status.label("status"), func.count(Worker.id).label("count"))
        .join(Worker.job)
        .filter(Job.owner_id == owner_id)
        .group_by(Worker.application_status)
        .all()
    )
    status_map = {row.status.value: row.count for row in status_rows}
    status_distribution = [
        {"status": status.value, "count": status_map.get(status.value, 0)}
        for status in ApplicationStatus
    ]

    # --- AI analysis status counts ---
    analysis_rows = (
        db.query(Worker.analysis_status.label("status"), func.count(Worker.id).label("count"))
        .join(Worker.job)
        .filter(Job.owner_id == owner_id)
        .group_by(Worker.analysis_status)
        .all()
    )
    analysis_map = {row.status.value: row.count for row in analysis_rows}
    analysis_status_counts = {status.value: analysis_map.get(status.value, 0) for status in AnalysisStatus}

    # --- Score distribution, one query, analyzed applications only ---
    bucket_expr = case(
        *[(Worker.ai_score.between(lo, hi), label) for label, lo, hi in SCORE_BUCKETS],
        else_=None,
    )
    score_rows = (
        db.query(bucket_expr.label("bucket"), func.count(Worker.id).label("count"))
        .join(Worker.job)
        .filter(Job.owner_id == owner_id, Worker.analysis_status == AnalysisStatus.COMPLETED)
        .group_by(bucket_expr)
        .all()
    )
    score_map = {row.bucket: row.count for row in score_rows if row.bucket is not None}
    score_distribution = [{"bucket": label, "count": score_map.get(label, 0)} for label, _, _ in SCORE_BUCKETS]

    # --- Hiring status counts (unchanged, real GROUP BY) ---
    hiring_rows = (
        db.query(Worker.hiring_status.label("status"), func.count(Worker.id).label("count"))
        .join(Worker.job)
        .filter(Job.owner_id == owner_id)
        .group_by(Worker.hiring_status)
        .all()
    )
    hiring_map = {row.status.value: row.count for row in hiring_rows}
    hiring_status_counts = {
        "strong_hire": hiring_map.get("strong_hire", 0),
        "hire": hiring_map.get("hire", 0),
        "weak_hire": hiring_map.get("weak_hire", 0),
        "do_not_hire": hiring_map.get("do_not_hire", 0),
    }

    # --- Interview status counts (worker-level field; kept for completeness) ---
    interview_status_rows = (
        db.query(Worker.interview_status.label("status"), func.count(Worker.id).label("count"))
        .join(Worker.job)
        .filter(Job.owner_id == owner_id)
        .group_by(Worker.interview_status)
        .all()
    )
    interview_status_map = {row.status.value: row.count for row in interview_status_rows}
    interview_status_counts = {
        "in_process": interview_status_map.get("in_process", 0),
        "completed": interview_status_map.get("completed", 0),
        "not_completed": interview_status_map.get("not_completed", 0),
    }

    # --- Average AI score, analyzed applications only ---
    avg_score_result = (
        db.query(func.avg(Worker.ai_score))
        .join(Worker.job)
        .filter(Job.owner_id == owner_id, Worker.analysis_status == AnalysisStatus.COMPLETED)
        .scalar()
    )
    avg_ai_score = round(float(avg_score_result or 0), 1)

    # --- Counts ---
    total_jobs = db.query(func.count(Job.id)).filter(Job.owner_id == owner_id).scalar() or 0
    total_applications = (
        db.query(func.count(Worker.id))
        .join(Job, Worker.job_id == Job.id)
        .filter(Job.owner_id == owner_id)
        .scalar()
        or 0
    )
    total_candidates = (
        db.query(func.count(Worker.id))
        .join(Job, Worker.job_id == Job.id)
        .filter(Job.owner_id == owner_id, Worker.candidate_at.is_not(None))
        .scalar()
        or 0
    )

    # --- Top jobs by application count ---
    top_job_rows = (
        db.query(
            Job.id.label("job_id"),
            Job.position.label("position"),
            Job.company_name.label("company_name"),
            func.count(Worker.id).label("applications_count"),
        )
        .outerjoin(Worker, Worker.job_id == Job.id)
        .filter(Job.owner_id == owner_id)
        .group_by(Job.id, Job.position, Job.company_name)
        .order_by(func.count(Worker.id).desc(), Job.id)
        .limit(8)
        .all()
    )
    top_jobs = [
        {
            "job_id": row.job_id,
            "position": row.position,
            "company_name": row.company_name,
            "applications_count": row.applications_count,
        }
        for row in top_job_rows
    ]

    return {
        "range": range_,
        "trend": trend,
        "previous_period": {"applications": prev_applications, "interviews": prev_interviews},
        "status_distribution": status_distribution,
        "analysis_status_counts": analysis_status_counts,
        "score_distribution": score_distribution,
        "hiring_status_counts": hiring_status_counts,
        "interview_status_counts": interview_status_counts,
        "avg_ai_score": avg_ai_score,
        "total_jobs": total_jobs,
        "total_applications": total_applications,
        "total_candidates": total_candidates,
        "top_jobs": top_jobs,
    }
