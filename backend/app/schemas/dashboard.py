"""Pydantic schemas for dashboard analytics and recent-activity responses."""

from datetime import datetime

from pydantic import BaseModel

from app.models.worker import HiringStatus

from app.models.worker import InterviewStatus


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


class HiringFunnel(BaseModel):
    """Hiring funnel counts by application status."""
    applied: int
    screening: int
    interview: int
    shortlisted: int
    hired: int
    rejected: int


class ScoreDistribution(BaseModel):
    """AI score distribution bucket."""
    bucket: str
    count: int


class WeeklyVolume(BaseModel):
    """Weekly applications and interviews count."""
    week: str
    applications: int
    interviews: int


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


class AnalyticsData(BaseModel):
    """Comprehensive analytics data for the Analytics page."""
    funnel: HiringFunnel
    score_distribution: list[ScoreDistribution]
    weekly_volume: list[WeeklyVolume]
    hiring_status_counts: HiringStatusCounts
    interview_status_counts: InterviewStatusCounts
    avg_ai_score: float
    total_jobs: int
    total_candidates: int