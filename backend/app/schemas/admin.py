"""Pydantic schemas for the superuser-only ``/api/admin`` endpoints.

Response models are explicit allowlists of fields: nothing is serialized
straight from an ORM object that could carry a password hash, Google id,
encrypted key or resume path.
"""

from datetime import datetime
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from app.models.interview import InterviewStatus as InterviewSessionStatus
from app.models.application import AnalysisStatus, ApplicationStatus, HiringStatus, InterviewStatus
from app.schemas.application_analysis import ApplicationAnalysis
from app.schemas.application import ApplicantAnswer, ApplicationInterviewSummary

T = TypeVar("T")

#: Hard cap on page size for every admin listing.
MAX_PAGE_SIZE = 100
SortOrder = Literal["asc", "desc"]


class Page(BaseModel, Generic[T]):
    """One page of a server-side paginated listing."""

    items: list[T]
    total: int
    page: int
    limit: int


# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------


class CountItem(BaseModel):
    """A labelled count (status distribution, provider breakdown, ...)."""

    key: str
    count: int


class AuditLogEntry(BaseModel):
    id: int
    created_at: datetime
    actor_user_id: int | None
    actor_email: str | None
    action: str
    resource_type: str
    resource_id: str | None
    details: dict[str, Any] | None
    ip_address: str | None
    user_agent: str | None
    request_id: str | None = None

    model_config = ConfigDict(from_attributes=True)


class OwnerOption(BaseModel):
    id: int
    full_name: str
    email: str


class FilterOptions(BaseModel):
    """Choices for the "HR owner" and "Company" dropdowns."""

    owners: list[OwnerOption]
    companies: list[str]


# ---------------------------------------------------------------------------
# Dashboard + analytics
# ---------------------------------------------------------------------------


class DashboardKpis(BaseModel):
    users_total: int
    users_active: int
    users_inactive: int
    admins: int
    jobs: int
    applications: int
    candidates: int
    interviews: int
    ai_analyzed: int
    ai_failed: int
    errors_24h: int


class SeriesPoint(BaseModel):
    """Counts of new records in one time bucket (day, week or month)."""

    date: str
    registrations: int = 0
    jobs: int = 0
    applications: int = 0
    interviews: int = 0
    ai_completed: int = 0
    ai_failed: int = 0


class AdminDashboard(BaseModel):
    kpis: DashboardKpis
    trend: list[SeriesPoint]
    recent_activity: list[AuditLogEntry]


class CompanyStat(BaseModel):
    company: str
    jobs: int
    applications: int


class TopJobStat(BaseModel):
    job_id: int
    position: str
    company_name: str
    owner_email: str
    applications: int


class RangeTotals(BaseModel):
    registrations: int
    jobs: int
    applications: int
    interviews: int
    ai_completed: int
    ai_failed: int


class UserTotals(BaseModel):
    total: int
    active: int
    inactive: int
    admins: int


class AdminAnalytics(BaseModel):
    range: str
    bucket: Literal["day", "week", "month"]
    series: list[SeriesPoint]
    totals: RangeTotals
    users: UserTotals
    application_status: list[CountItem]
    analysis_status: list[CountItem]
    hiring_status: list[CountItem]
    interview_status: list[CountItem]
    score_distribution: list[CountItem]
    top_companies: list[CompanyStat]
    top_jobs: list[TopJobStat]
    avg_applications_per_job: float
    avg_ai_score: float | None


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


class AdminUserRow(BaseModel):
    id: int
    email: str
    full_name: str
    is_active: bool
    is_superuser: bool
    has_password: bool
    google_linked: bool
    created_at: datetime
    last_login_at: datetime | None
    jobs_count: int
    applications_count: int


class UserStats(BaseModel):
    jobs: int
    applications: int
    candidates: int
    interviews: int
    ai_analyses: int
    ai_runs_failed: int


class AdminJobBrief(BaseModel):
    id: int
    position: str
    company_name: str
    applications_count: int
    created_at: datetime


class AdminApplicationBrief(BaseModel):
    id: int
    name: str
    position: str
    company_name: str
    application_status: ApplicationStatus
    analysis_status: AnalysisStatus
    is_candidate: bool
    submitted_at: datetime


class AdminUserDetail(AdminUserRow):
    stats: UserStats
    ai_provider_source: Literal["default", "custom"]
    recent_jobs: list[AdminJobBrief]
    recent_applications: list[AdminApplicationBrief]
    recent_activity: list[AuditLogEntry]


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------


class AdminJobRow(BaseModel):
    id: int
    position: str
    company_name: str
    owner_id: int
    owner_email: str
    owner_name: str
    applications_count: int
    candidates_count: int
    analyzed_count: int
    created_at: datetime


class AdminJobDetail(AdminJobRow):
    description: str
    required_skills: str
    required_experience: str
    has_public_form: bool
    status_breakdown: list[CountItem]


# ---------------------------------------------------------------------------
# Applications / candidates
# ---------------------------------------------------------------------------


class AdminApplicationRow(BaseModel):
    id: int
    name: str
    email: str
    job_id: int
    position: str
    company_name: str
    owner_id: int
    owner_email: str
    owner_name: str
    application_status: ApplicationStatus
    analysis_status: AnalysisStatus
    #: Only set once an analysis completed (otherwise the stored 0 is meaningless).
    ai_score: float | None
    #: The AI's suggestion, kept separate from the human ``hiring_status``.
    ai_recommendation: str | None
    hiring_status: HiringStatus
    interview_status: InterviewStatus
    is_candidate: bool
    candidate_at: datetime | None
    submitted_at: datetime


class AdminApplicationDetail(AdminApplicationRow):
    analysis_error: str | None
    analysis: ApplicationAnalysis | None
    responses: list[ApplicantAnswer]
    interviews: list[ApplicationInterviewSummary]
    has_resume: bool


class ApplicationSummary(BaseModel):
    total: int
    analysis_status: dict[str, int]
    application_status: dict[str, int]
    hiring_status: dict[str, int]
    interview_status: dict[str, int]


class AdminApplicationPage(Page[AdminApplicationRow]):
    summary: ApplicationSummary


# ---------------------------------------------------------------------------
# Interviews
# ---------------------------------------------------------------------------


class AdminInterviewRow(BaseModel):
    id: int
    candidate_id: int
    candidate_name: str
    job_id: int
    position: str
    company_name: str
    hr_id: int
    hr_email: str
    hr_name: str
    interviewer: str
    scheduled_at: datetime
    duration_minutes: int
    status: InterviewSessionStatus
    created_at: datetime


class InterviewSummary(BaseModel):
    total: int
    upcoming: int
    completed: int
    cancelled: int
    #: Still "upcoming" although the scheduled time has passed.
    overdue: int
    #: Candidate-level interview progress (``applications.interview_status``).
    candidate_progress: dict[str, int]


class AdminInterviewPage(Page[AdminInterviewRow]):
    summary: InterviewSummary


# ---------------------------------------------------------------------------
# AI monitoring
# ---------------------------------------------------------------------------


class AIRunTotals(BaseModel):
    total: int
    completed: int
    failed: int
    success_rate: float | None
    avg_duration_ms: int | None


class AIBatchRow(BaseModel):
    id: int
    owner_email: str | None
    status: str
    total: int
    successful: int
    failed: int
    skipped: int
    created_at: datetime
    finished_at: datetime | None


class AIPlatformProvider(BaseModel):
    provider: str
    model: str | None
    api_key_configured: bool
    custom_provider_users: int


class AIOverview(BaseModel):
    #: Attempts recorded since monitoring was enabled.
    runs_all_time: AIRunTotals
    runs_24h: AIRunTotals
    #: Current state of every application (includes pre-monitoring history).
    analysis_status: list[CountItem]
    avg_score: float | None
    providers: list[CountItem]
    failure_categories: list[CountItem]
    recent_batches: list[AIBatchRow]
    platform_provider: AIPlatformProvider


class AIRunRow(BaseModel):
    id: int
    created_at: datetime
    kind: str
    status: str
    owner_email: str | None
    job_id: int | None
    position: str | None
    company_name: str | None
    application_id: int | None
    provider: str | None
    model: str | None
    source: str | None
    duration_ms: int | None
    score: float | None
    error_category: str | None
    http_status: int | None
    error_message: str | None


# ---------------------------------------------------------------------------
# Audit + errors
# ---------------------------------------------------------------------------


class AuditMeta(BaseModel):
    actions: list[str]
    resource_types: list[str]


class SystemErrorRow(BaseModel):
    id: int
    created_at: datetime
    request_id: str | None
    method: str
    path: str
    status_code: int
    error_type: str
    message: str
    user_id: int | None
    user_email: str | None


class SystemErrorSummary(BaseModel):
    last_24h: int
    last_7d: int
    by_status_7d: list[CountItem]


class SystemErrorPage(Page[SystemErrorRow]):
    summary: SystemErrorSummary


# ---------------------------------------------------------------------------
# Health + settings
# ---------------------------------------------------------------------------

#: "configured" = settings present but not verified (no external call is made).
HealthStatus = Literal["healthy", "configured", "degraded", "down", "not_configured"]


class HealthComponent(BaseModel):
    key: str
    status: HealthStatus
    latency_ms: float | None = None
    #: Short, safe explanation (never a connection string or credential).
    detail: str = ""
    metrics: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class HealthReport(BaseModel):
    status: Literal["healthy", "degraded", "down"]
    checked_at: datetime
    components: list[HealthComponent]


class RuntimeSettings(BaseModel):
    registration_enabled: bool
    updated_at: datetime | None
    updated_by_email: str | None


class AdminSettings(BaseModel):
    runtime: RuntimeSettings
    #: Environment configuration as status flags; see platform_settings service.
    configuration: dict[str, dict[str, Any]]


class RuntimeSettingsUpdate(BaseModel):
    """Only runtime switches are editable; environment values never are."""

    registration_enabled: bool | None = None

    model_config = ConfigDict(extra="forbid")
