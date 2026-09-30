"""Dashboard analytics and recent-leads endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.crud import job as job_crud
from app.crud import application as application_crud
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.dashboard import (
    AnalyticsData,
    AnalyticsOverview,
    RecentJob,
    RecentLead,
)
from app.services import dashboard_analytics
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
    applications = application_crud.get_recent_applications(db, current_user.id, limit)
    return [
        RecentLead(
            id=application.id,
            name=application.name,
            email=application.email,
            company_name=application.job.company_name,
            position=application.job.position,
            hiring_status=application.hiring_status,
            created_at=application.created_at,
        )
        for application in applications
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


@router.get("/analytics", response_model=AnalyticsData)
def get_analytics(
    range_param: str = Query("30d", alias="range", pattern="^(7d|30d|90d)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AnalyticsData:
    """Return comprehensive hiring analytics for the current user.

    Includes the applications/interviews trend for the selected range, the
    real application-status distribution, AI processing counts, score
    distribution, hiring-decision counts and the top jobs by applications.
    """
    data = dashboard_analytics.get_analytics(db, current_user.id, range_param)  # type: ignore[arg-type]
    return AnalyticsData(**data)
