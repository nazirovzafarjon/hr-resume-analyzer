"""Pydantic schemas for dashboard analytics and recent-activity responses."""

from datetime import datetime

from pydantic import BaseModel

from app.models.application import HiringStatus

from app.models.application import InterviewStatus


class CategoryBreakdown(BaseModel):
    """Counts grouped for a single category value (e.g. a company name)."""
    category: str
    jobs: int
    candidates: int


class AnalyticsOverview(BaseModel):
    """High-level hiring analytics for the current HR user."""
    total_jobs: int
    total_candidates: int
    total_leads: int
    group_by: str
    breakdown: list[CategoryBreakdown]


class RecentLead(BaseModel):
    """A recently received resume/candidate application."""
    id: int
    name: str
    email: str
    company_name: str
    position: str
    hiring_status: HiringStatus
    created_at: datetime


class RecentJob(BaseModel):
    """A recently created job and its hiring progress."""
    id: int
    company_name: str
    position: str
    leads_count: int
    created_at: datetime


class TrendPoint(BaseModel):
    """Applications and interviews recorded in one time bucket (day or week)."""
    date: str
    applications: int
    interviews: int


class PreviousPeriod(BaseModel):
    """Totals for the period immediately preceding the selected range."""
    applications: int
    interviews: int


class StatusCount(BaseModel):
    """Count of applications currently in one real `ApplicationStatus` value."""
    status: str
    count: int


class ScoreDistribution(BaseModel):
    """AI score distribution bucket."""
    bucket: str
    count: int


class AnalysisStatusCounts(BaseModel):
    """Counts by AI analysis processing state."""
    new: int
    pending: int
    analyzing: int
    completed: int
    failed: int


class HiringStatusCounts(BaseModel):
    """Counts by hiring decision status."""
    strong_hire: int
    hire: int
    weak_hire: int
    do_not_hire: int


class InterviewStatusCounts(BaseModel):
    """Counts by interview progress status."""
    in_process: int
    completed: int
    not_completed: int


class TopJob(BaseModel):
    """A job ranked by how many applications it has received."""
    job_id: int
    position: str
    company_name: str
    applications_count: int


class AnalyticsData(BaseModel):
    """Comprehensive analytics data for the Dashboard and Analytics pages."""
    range: str
    trend: list[TrendPoint]
    previous_period: PreviousPeriod
    status_distribution: list[StatusCount]
    analysis_status_counts: AnalysisStatusCounts
    score_distribution: list[ScoreDistribution]
    hiring_status_counts: HiringStatusCounts
    interview_status_counts: InterviewStatusCounts
    avg_ai_score: float
    total_jobs: int
    total_applications: int
    total_candidates: int
    top_jobs: list[TopJob]
