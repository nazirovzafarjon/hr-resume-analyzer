"""Dashboard analytics and recent-leads endpoints."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.crud import job as job_crud
from app.crud import worker as worker_crud
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.worker import ApplicationStatus, Worker
from app.models.job import Job
from app.schemas.dashboard import (
    AnalyticsOverview,
    HiringFunnel,
    HiringStatusCounts,
    InterviewStatusCounts,
    RecentJob,
    RecentLead,
    ScoreDistribution,
    WeeklyVolume,
)
from app.services import job as job_service

router = APIRouter()


@router.get("/overview", response_model=AnalyticsOverview)
def get_overview(
    category: str = Query("company", description="Analytics grouping"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AnalyticsOverview:
    """Return hiring analytics grouped by the requested category."""
    try:
        overview = job_service.job_analytics(db, current_user.id, category)
        return AnalyticsOverview(**overview)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@router.get("/recent-leads", response_model=list[RecentLead])
def get_recent_leads(
    limit: int = Query(5, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[RecentLead]:
    """Return the most recent candidate applications for the current user."""
    workers = worker_crud.get_recent_workers(db, current_user.id, limit)
    return [
        RecentLead(
            id=worker.id,
            name=worker.name,
            email=worker.email,
            company_name=worker.job.company_name,
            position=worker.job.position,
            hiring_status=worker.hiring_status,
            created_at=worker.created_at,
        )
        for worker in workers
    ]


@router.get("/recent-jobs", response_model=list[RecentJob])
def get_recent_jobs(
    limit: int = Query(5, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[RecentJob]:
    """Return the most recent jobs created by the current user."""
    jobs = job_crud.get_recent_jobs(db, current_user.id, limit)
    return [
        RecentJob(
            id=job.id,
            company_name=job.company_name,
            position=job.position,
            leads_count=job.leads_count,
            created_at=job.created_at,
        )
        for job in jobs
    ]


@router.get("/analytics")
def get_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return comprehensive analytics for the current user.

    Includes hiring funnel, score distribution, weekly volume, and status counts.
    """
    owner_id = current_user.id

    # Hiring funnel: count applications by application_status
    funnel_rows = (
        db.query(
            Worker.application_status.label("status"),
            func.count(Worker.id).label("count"),
        )
        .join(Worker.job)
        .filter(Job.owner_id == owner_id)
        .group_by(Worker.application_status)
        .all()
    )

    funnel_map = {row.status.value: row.count for row in funnel_rows}
    funnel = HiringFunnel(
        applied=funnel_map.get("new", 0),
        screening=funnel_map.get("reviewing", 0),
        interview=funnel_map.get("interview", 0),
        shortlisted=funnel_map.get("shortlisted", 0),
        hired=funnel_map.get("hired", 0),
        rejected=funnel_map.get("rejected", 0),
    )

    # AI score distribution: count applications in score buckets
    score_buckets = [
        ("0-49", 0, 49),
        ("50-59", 50, 59),
        ("60-69", 60, 69),
        ("70-79", 70, 79),
        ("80-89", 80, 89),
        ("90-100", 90, 100),
    ]

    distribution_rows = []
    for label, min_score, max_score in score_buckets:
        count = (
            db.query(func.count(Worker.id))
            .join(Worker.job)
            .filter(Job.owner_id == owner_id)
            .filter(Worker.ai_score >= min_score)
            .filter(Worker.ai_score <= max_score)
            .scalar()
            or 0
        )
        distribution_rows.append(ScoreDistribution(bucket=label, count=count))

    # Weekly volume: applications and interviews per week (last 6 weeks)
    now = datetime.now(timezone.utc)
    weekly_data = []
    for i in range(6):
        week_end = now - timedelta(weeks=i)
        week_start = week_end - timedelta(days=6)
        label = week_start.strftime("%b %d")

        apps_count = (
            db.query(func.count(Worker.id))
            .join(Worker.job)
            .filter(Job.owner_id == owner_id)
            .filter(Worker.created_at >= week_start)
            .filter(Worker.created_at <= week_end)
            .scalar()
            or 0
        )

        interviews_count = (
            db.query(func.count(Worker.id))
            .join(Worker.job)
            .filter(Job.owner_id == owner_id)
            .filter(Worker.created_at >= week_start)
            .filter(Worker.created_at <= week_end)
            .filter(Worker.interview_status != "not_completed")
            .scalar()
            or 0
        )

        weekly_data.append(
            WeeklyVolume(week=label, applications=apps_count, interviews=interviews_count)
        )

    # Hiring status counts
    hiring_status_rows = (
        db.query(
            Worker.hiring_status.label("status"),
            func.count(Worker.id).label("count"),
        )
        .join(Worker.job)
        .filter(Job.owner_id == owner_id)
        .group_by(Worker.hiring_status)
        .all()
    )
    hiring_counts_map = {row.status.value: row.count for row in hiring_status_rows}
    hiring_status_counts = HiringStatusCounts(
        strong_hire=hiring_counts_map.get("strong_hire", 0),
        hire=hiring_counts_map.get("hire", 0),
        weak_hire=hiring_counts_map.get("weak_hire", 0),
        do_not_hire=hiring_counts_map.get("do_not_hire", 0),
    )

    # Interview status counts
    interview_status_rows = (
        db.query(
            Worker.interview_status.label("status"),
            func.count(Worker.id).label("count"),
        )
        .join(Worker.job)
        .filter(Job.owner_id == owner_id)
        .group_by(Worker.interview_status)
        .all()
    )
    interview_counts_map = {row.status.value: row.count for row in interview_status_rows}
    interview_status_counts = InterviewStatusCounts(
        in_process=interview_counts_map.get("in_process", 0),
        completed=interview_counts_map.get("completed", 0),
        not_completed=interview_counts_map.get("not_completed", 0),
    )

    # Average AI score
    avg_score_result = (
        db.query(func.avg(Worker.ai_score))
        .join(Worker.job)
        .filter(Job.owner_id == owner_id)
        .scalar()
    )
    avg_score = round(float(avg_score_result or 0), 1)

    # Total counts
    total_jobs = (
        db.query(func.count(Job.id)).filter(Job.owner_id == owner_id).scalar() or 0
    )
    total_candidates = (
        db.query(func.count(Worker.id))
        .join(Job, Worker.job_id == Job.id)
        .filter(Job.owner_id == owner_id)
        .scalar()
        or 0
    )

    return {
        "funnel": funnel,
        "score_distribution": distribution_rows,
        "weekly_volume": list(reversed(weekly_data)),  # Oldest first
        "hiring_status_counts": hiring_status_counts,
        "interview_status_counts": interview_status_counts,
        "avg_ai_score": avg_score,
        "total_jobs": total_jobs,
        "total_candidates": total_candidates,
    }