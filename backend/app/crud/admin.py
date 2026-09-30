"""Platform-wide read queries for the admin panel.

Unlike the HR-facing CRUD modules, nothing here is scoped to an owner: these
functions are only reachable through superuser-protected routes.

Every listing:
* aggregates per-row counts in grouped subqueries joined once (no N+1),
* sorts only through an allowlist of columns (user input never becomes SQL),
* searches with bound, wildcard-escaped ILIKE patterns,
* returns ``(rows, total)`` for server-side pagination.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import Select, and_, distinct, func, or_, select
from sqlalchemy.orm import Session

from app.crud.query_utils import contains_pattern, paginate
from app.models.ai_analysis_run import AIAnalysisRun
from app.models.interview import Interview, InterviewStatus as InterviewSessionStatus
from app.models.job import Job
from app.models.user import User
from app.models.application import (
    AnalysisStatus,
    ApplicationStatus,
    HiringStatus,
    InterviewStatus,
    Application,
)

#: Analysis filter values exposed by the API -> the stored statuses they cover.
ANALYSIS_FILTERS: dict[str, tuple[AnalysisStatus, ...]] = {
    "analyzed": (AnalysisStatus.COMPLETED,),
    "not_analyzed": (AnalysisStatus.NEW, AnalysisStatus.PENDING),
    "analyzing": (AnalysisStatus.ANALYZING,),
    "failed": (AnalysisStatus.FAILED,),
}


def _ordered(stmt: Select[Any], column: Any, order: str, tiebreak: Any) -> Select[Any]:
    """Apply a validated sort column plus a stable id tiebreak."""
    primary = column.asc().nulls_last() if order == "asc" else column.desc().nulls_last()
    return stmt.order_by(primary, tiebreak.desc())


def _date_range(stmt: Select[Any], column: Any, date_from: datetime | None, date_to: datetime | None):
    if date_from is not None:
        stmt = stmt.where(column >= date_from)
    if date_to is not None:
        stmt = stmt.where(column <= date_to)
    return stmt


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


def _jobs_per_owner():
    return (
        select(Job.owner_id.label("owner_id"), func.count(Job.id).label("jobs_count"))
        .group_by(Job.owner_id)
        .subquery()
    )


def _applications_per_owner():
    return (
        select(Job.owner_id.label("owner_id"), func.count(Application.id).label("applications_count"))
        .join(Application, Application.job_id == Job.id)
        .group_by(Job.owner_id)
        .subquery()
    )


def list_users(
    db: Session,
    *,
    page: int,
    limit: int,
    search: str | None = None,
    is_active: bool | None = None,
    is_superuser: bool | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    sort: str = "created_at",
    order: str = "desc",
) -> tuple[list[Any], int]:
    """Rows are ``(User, jobs_count, applications_count)``."""
    jobs_sq = _jobs_per_owner()
    apps_sq = _applications_per_owner()
    jobs_count = func.coalesce(jobs_sq.c.jobs_count, 0)
    apps_count = func.coalesce(apps_sq.c.applications_count, 0)

    stmt = (
        select(User, jobs_count.label("jobs_count"), apps_count.label("applications_count"))
        .outerjoin(jobs_sq, jobs_sq.c.owner_id == User.id)
        .outerjoin(apps_sq, apps_sq.c.owner_id == User.id)
    )
    if search:
        pattern = contains_pattern(search)
        stmt = stmt.where(
            or_(User.full_name.ilike(pattern, escape="\\"), User.email.ilike(pattern, escape="\\"))
        )
    if is_active is not None:
        stmt = stmt.where(User.is_active.is_(is_active))
    if is_superuser is not None:
        stmt = stmt.where(User.is_superuser.is_(is_superuser))
    stmt = _date_range(stmt, User.created_at, date_from, date_to)

    sort_columns = {
        "name": User.full_name,
        "email": User.email,
        "created_at": User.created_at,
        "last_login_at": User.last_login_at,
        "jobs": jobs_count,
        "applications": apps_count,
    }
    stmt = _ordered(stmt, sort_columns[sort], order, User.id)
    return paginate(db, stmt, page, limit)


@dataclass
class UserActivityCounts:
    jobs: int
    applications: int
    candidates: int
    interviews: int
    ai_analyses: int
    ai_runs_failed: int


def user_activity_counts(db: Session, user_id: int) -> UserActivityCounts:
    """Aggregate a single user's footprint in a handful of COUNT queries."""
    jobs = db.execute(select(func.count(Job.id)).where(Job.owner_id == user_id)).scalar_one()
    apps, candidates, analyzed = db.execute(
        select(
            func.count(Application.id),
            func.count(Application.id).filter(Application.candidate_at.is_not(None)),
            func.count(Application.id).filter(Application.analysis_status == AnalysisStatus.COMPLETED),
        )
        .join(Job, Job.id == Application.job_id)
        .where(Job.owner_id == user_id)
    ).one()
    interviews = db.execute(
        select(func.count(Interview.id)).where(Interview.hr_id == user_id)
    ).scalar_one()
    failed_runs = db.execute(
        select(func.count(AIAnalysisRun.id)).where(
            AIAnalysisRun.owner_id == user_id, AIAnalysisRun.status == "failed"
        )
    ).scalar_one()
    return UserActivityCounts(
        jobs=int(jobs),
        applications=int(apps),
        candidates=int(candidates),
        interviews=int(interviews),
        ai_analyses=int(analyzed),
        ai_runs_failed=int(failed_runs),
    )


def filter_owners(db: Session, limit: int = 500) -> list[User]:
    """Users that own at least one job, for the "HR owner" filter dropdowns."""
    stmt = (
        select(User)
        .where(select(Job.id).where(Job.owner_id == User.id).exists())
        .order_by(User.full_name, User.id)
        .limit(limit)
    )
    return list(db.execute(stmt).scalars())


def filter_companies(db: Session, limit: int = 500) -> list[str]:
    """Distinct company names across all jobs, for the company filter."""
    stmt = select(distinct(Job.company_name)).order_by(Job.company_name).limit(limit)
    return [name for name in db.execute(stmt).scalars() if name]


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------


def _application_counts_per_job():
    return (
        select(
            Application.job_id.label("job_id"),
            func.count(Application.id).label("applications_count"),
            func.count(Application.id).filter(Application.candidate_at.is_not(None)).label("candidates_count"),
            func.count(Application.id)
            .filter(Application.analysis_status == AnalysisStatus.COMPLETED)
            .label("analyzed_count"),
        )
        .group_by(Application.job_id)
        .subquery()
    )


def list_jobs(
    db: Session,
    *,
    page: int,
    limit: int,
    search: str | None = None,
    owner_id: int | None = None,
    company: str | None = None,
    job_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    sort: str = "created_at",
    order: str = "desc",
) -> tuple[list[Any], int]:
    """Rows are ``(Job, owner_email, owner_name, applications, candidates, analyzed)``."""
    counts = _application_counts_per_job()
    applications = func.coalesce(counts.c.applications_count, 0)
    stmt = (
        select(
            Job,
            User.email,
            User.full_name,
            applications.label("applications_count"),
            func.coalesce(counts.c.candidates_count, 0).label("candidates_count"),
            func.coalesce(counts.c.analyzed_count, 0).label("analyzed_count"),
        )
        .join(User, User.id == Job.owner_id)
        .outerjoin(counts, counts.c.job_id == Job.id)
    )
    if search:
        pattern = contains_pattern(search)
        stmt = stmt.where(
            or_(
                Job.position.ilike(pattern, escape="\\"),
                Job.company_name.ilike(pattern, escape="\\"),
                User.email.ilike(pattern, escape="\\"),
            )
        )
    if owner_id is not None:
        stmt = stmt.where(Job.owner_id == owner_id)
    if company:
        stmt = stmt.where(Job.company_name == company)
    if job_id is not None:
        stmt = stmt.where(Job.id == job_id)
    stmt = _date_range(stmt, Job.created_at, date_from, date_to)

    sort_columns = {
        "created_at": Job.created_at,
        "position": Job.position,
        "company": Job.company_name,
        "applications": applications,
    }
    stmt = _ordered(stmt, sort_columns[sort], order, Job.id)
    return paginate(db, stmt, page, limit)


def job_status_breakdown(db: Session, job_id: int) -> dict[str, int]:
    """Application-status counts for one job."""
    rows = db.execute(
        select(Application.application_status, func.count(Application.id))
        .where(Application.job_id == job_id)
        .group_by(Application.application_status)
    ).all()
    return {status.value: int(count) for status, count in rows}


# ---------------------------------------------------------------------------
# Applications / candidates (both are ``applications`` rows)
# ---------------------------------------------------------------------------


@dataclass
class ApplicationFilters:
    candidates_only: bool = False
    search: str | None = None
    owner_id: int | None = None
    company: str | None = None
    job_id: int | None = None
    analysis: str | None = None
    application_status: ApplicationStatus | None = None
    hiring_status: HiringStatus | None = None
    interview_status: InterviewStatus | None = None
    score_min: float | None = None
    score_max: float | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None


def list_applications(
    db: Session,
    filters: ApplicationFilters,
    *,
    page: int,
    limit: int,
    sort: str = "submitted_at",
    order: str = "desc",
) -> tuple[list[Any], int]:
    """Rows are ``(Application, Job, owner_email, owner_name)``."""
    stmt = (
        select(Application, Job, User.email, User.full_name)
        .join(Job, Job.id == Application.job_id)
        .join(User, User.id == Job.owner_id)
    )
    if filters.candidates_only:
        stmt = stmt.where(Application.candidate_at.is_not(None))
    if filters.search:
        pattern = contains_pattern(filters.search)
        stmt = stmt.where(
            or_(
                Application.name.ilike(pattern, escape="\\"),
                Application.email.ilike(pattern, escape="\\"),
                Job.position.ilike(pattern, escape="\\"),
                Job.company_name.ilike(pattern, escape="\\"),
            )
        )
    if filters.owner_id is not None:
        stmt = stmt.where(Job.owner_id == filters.owner_id)
    if filters.company:
        stmt = stmt.where(Job.company_name == filters.company)
    if filters.job_id is not None:
        stmt = stmt.where(Application.job_id == filters.job_id)
    if filters.analysis:
        stmt = stmt.where(Application.analysis_status.in_(ANALYSIS_FILTERS[filters.analysis]))
    if filters.application_status is not None:
        stmt = stmt.where(Application.application_status == filters.application_status)
    if filters.hiring_status is not None:
        stmt = stmt.where(Application.hiring_status == filters.hiring_status)
    if filters.interview_status is not None:
        stmt = stmt.where(Application.interview_status == filters.interview_status)
    # A score only means something once an analysis completed (unanalysed
    # rows default to 0), so a score filter implies "analyzed".
    if filters.score_min is not None or filters.score_max is not None:
        stmt = stmt.where(Application.analysis_status == AnalysisStatus.COMPLETED)
        if filters.score_min is not None:
            stmt = stmt.where(Application.ai_score >= filters.score_min)
        if filters.score_max is not None:
            stmt = stmt.where(Application.ai_score <= filters.score_max)
    stmt = _date_range(stmt, Application.submitted_at, filters.date_from, filters.date_to)

    sort_columns = {
        "submitted_at": Application.submitted_at,
        "candidate_at": Application.candidate_at,
        "name": Application.name,
        "ai_score": Application.ai_score,
    }
    stmt = _ordered(stmt, sort_columns[sort], order, Application.id)
    return paginate(db, stmt, page, limit)


def application_summary(db: Session, candidates_only: bool) -> dict[str, Any]:
    """Platform-wide status counts shown above the applications/candidates table."""

    def scoped(stmt: Select[Any]) -> Select[Any]:
        return stmt.where(Application.candidate_at.is_not(None)) if candidates_only else stmt

    def grouped(column: Any) -> dict[str, int]:
        stmt = scoped(select(column, func.count(Application.id)).group_by(column))
        return {value.value: int(count) for value, count in db.execute(stmt).all()}

    total = db.execute(scoped(select(func.count(Application.id)))).scalar_one()
    return {
        "total": int(total),
        "analysis_status": grouped(Application.analysis_status),
        "application_status": grouped(Application.application_status),
        "hiring_status": grouped(Application.hiring_status),
        "interview_status": grouped(Application.interview_status),
    }


# ---------------------------------------------------------------------------
# Interviews
# ---------------------------------------------------------------------------


def list_interviews(
    db: Session,
    *,
    page: int,
    limit: int,
    search: str | None = None,
    owner_id: int | None = None,
    company: str | None = None,
    job_id: int | None = None,
    status: InterviewSessionStatus | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    sort: str = "scheduled_at",
    order: str = "desc",
) -> tuple[list[Any], int]:
    """Rows are ``(Interview, Application, Job, hr_email, hr_name)``."""
    stmt = (
        select(Interview, Application, Job, User.email, User.full_name)
        .join(Application, Application.id == Interview.candidate_id)
        .join(Job, Job.id == Application.job_id)
        .join(User, User.id == Interview.hr_id)
    )
    if search:
        pattern = contains_pattern(search)
        stmt = stmt.where(
            or_(
                Application.name.ilike(pattern, escape="\\"),
                Interview.interviewer.ilike(pattern, escape="\\"),
                Job.position.ilike(pattern, escape="\\"),
            )
        )
    if owner_id is not None:
        stmt = stmt.where(Interview.hr_id == owner_id)
    if company:
        stmt = stmt.where(Job.company_name == company)
    if job_id is not None:
        stmt = stmt.where(Job.id == job_id)
    if status is not None:
        stmt = stmt.where(Interview.status == status)
    stmt = _date_range(stmt, Interview.scheduled_at, date_from, date_to)

    sort_columns = {"scheduled_at": Interview.scheduled_at, "created_at": Interview.created_at}
    stmt = _ordered(stmt, sort_columns[sort], order, Interview.id)
    return paginate(db, stmt, page, limit)


def interview_summary(db: Session, now: datetime) -> dict[str, int]:
    """Session counts; "overdue" = still marked upcoming but already in the past."""
    total, upcoming, completed, cancelled, overdue = db.execute(
        select(
            func.count(Interview.id),
            func.count(Interview.id).filter(
                and_(Interview.status == InterviewSessionStatus.UPCOMING, Interview.scheduled_at >= now)
            ),
            func.count(Interview.id).filter(Interview.status == InterviewSessionStatus.COMPLETED),
            func.count(Interview.id).filter(Interview.status == InterviewSessionStatus.CANCELLED),
            func.count(Interview.id).filter(
                and_(Interview.status == InterviewSessionStatus.UPCOMING, Interview.scheduled_at < now)
            ),
        )
    ).one()
    return {
        "total": int(total),
        "upcoming": int(upcoming),
        "completed": int(completed),
        "cancelled": int(cancelled),
        "overdue": int(overdue),
    }
