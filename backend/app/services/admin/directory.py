"""Admin read views: users, jobs, applications, candidates and interviews.

Turns the platform-wide query rows from ``crud.admin`` into the explicit
response schemas in ``schemas.admin`` and composes the detail views. Reads
only, with one exception: :func:`delete_job` (admin moderation), which is
audited.
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud import admin as admin_crud
from app.crud import ai_provider_config as ai_config_crud
from app.crud import audit_log as audit_crud
from app.crud import job as job_crud
from app.crud import application as application_crud
from app.crud.admin import ApplicationFilters
from app.models.job import Job
from app.models.user import User
from app.models.application import AnalysisStatus, Application
from app.schemas import admin as schemas
from app.schemas.application import ApplicantAnswer, ApplicationInterviewSummary
from app.services import audit
from app.services.application_analysis import stored_analysis
from app.services.audit import AuditAction, AuditContext, AuditResource

_RECENT_ITEMS = 5


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


def _user_row(user: User, jobs_count: int, applications_count: int) -> schemas.AdminUserRow:
    return schemas.AdminUserRow(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        has_password=user.has_password,
        google_linked=user.google_id is not None,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        jobs_count=int(jobs_count),
        applications_count=int(applications_count),
    )


def list_users(db: Session, *, page: int, limit: int, **filters: Any) -> schemas.Page[schemas.AdminUserRow]:
    rows, total = admin_crud.list_users(db, page=page, limit=limit, **filters)
    return schemas.Page[schemas.AdminUserRow](
        items=[_user_row(user, jobs, apps) for user, jobs, apps in rows],
        total=total,
        page=page,
        limit=limit,
    )


def get_user_detail(db: Session, user: User) -> schemas.AdminUserDetail:
    counts = admin_crud.user_activity_counts(db, user.id)
    recent_jobs, _ = admin_crud.list_jobs(db, page=1, limit=_RECENT_ITEMS, owner_id=user.id)
    recent_applications, _ = admin_crud.list_applications(
        db, ApplicationFilters(owner_id=user.id), page=1, limit=_RECENT_ITEMS
    )
    config = ai_config_crud.get_config(db, user.id)
    return schemas.AdminUserDetail(
        **_user_row(user, counts.jobs, counts.applications).model_dump(),
        stats=schemas.UserStats(**counts.__dict__),
        ai_provider_source="custom" if config is not None and config.is_active else "default",
        recent_jobs=[
            schemas.AdminJobBrief(
                id=job.id,
                position=job.position,
                company_name=job.company_name,
                applications_count=int(apps),
                created_at=job.created_at,
            )
            for job, _email, _name, apps, _cands, _analyzed in recent_jobs
        ],
        recent_applications=[
            schemas.AdminApplicationBrief(
                id=application.id,
                name=application.name,
                position=job.position,
                company_name=job.company_name,
                application_status=application.application_status,
                analysis_status=application.analysis_status,
                is_candidate=application.is_candidate,
                submitted_at=application.submitted_at,
            )
            for application, job, _email, _name in recent_applications
        ],
        recent_activity=[
            schemas.AuditLogEntry.model_validate(entry)
            for entry in audit_crud.recent_entries(db, 10, actor_user_id=user.id)
        ],
    )


def filter_options(db: Session) -> schemas.FilterOptions:
    return schemas.FilterOptions(
        owners=[
            schemas.OwnerOption(id=user.id, full_name=user.full_name, email=user.email)
            for user in admin_crud.filter_owners(db)
        ],
        companies=admin_crud.filter_companies(db),
    )


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------


def _job_row(job: Job, email: str, name: str, apps: int, cands: int, analyzed: int) -> schemas.AdminJobRow:
    return schemas.AdminJobRow(
        id=job.id,
        position=job.position,
        company_name=job.company_name,
        owner_id=job.owner_id,
        owner_email=email,
        owner_name=name,
        applications_count=int(apps),
        candidates_count=int(cands),
        analyzed_count=int(analyzed),
        created_at=job.created_at,
    )


def list_jobs(db: Session, *, page: int, limit: int, **filters: Any) -> schemas.Page[schemas.AdminJobRow]:
    rows, total = admin_crud.list_jobs(db, page=page, limit=limit, **filters)
    return schemas.Page[schemas.AdminJobRow](
        items=[_job_row(*row) for row in rows], total=total, page=page, limit=limit
    )


def get_job_detail(db: Session, job_id: int) -> schemas.AdminJobDetail | None:
    rows, _ = admin_crud.list_jobs(db, page=1, limit=1, job_id=job_id)
    if not rows:
        return None
    job = rows[0][0]
    breakdown = admin_crud.job_status_breakdown(db, job.id)
    return schemas.AdminJobDetail(
        **_job_row(*rows[0]).model_dump(),
        description=job.description or "",
        required_skills=job.required_skills or "",
        required_experience=job.required_experience or "",
        has_public_form=job.application_form is not None,
        status_breakdown=[schemas.CountItem(key=key, count=count) for key, count in breakdown.items()],
    )


def delete_job(db: Session, admin: User, job: Job, context: AuditContext | None = None) -> None:
    """Moderation delete of any HR user's job (its applications cascade).

    Ownership is never transferred or changed; the job is simply removed and
    the audit row records whose job it was.
    """
    details = {
        "position": job.position,
        "company": job.company_name,
        "owner_id": job.owner_id,
        "by_admin": True,
    }
    job_crud.delete_job(db, job.id)
    audit.record(
        db,
        AuditAction.DELETE_JOB,
        resource_type=AuditResource.JOB,
        resource_id=job.id,
        actor=admin,
        details=details,
        context=context,
    )


# ---------------------------------------------------------------------------
# Applications / candidates
# ---------------------------------------------------------------------------


def _application_row(application: Application, job: Job, owner_email: str, owner_name: str) -> dict[str, Any]:
    analyzed = application.analysis_status == AnalysisStatus.COMPLETED
    details = application.ai_analysis_details if isinstance(application.ai_analysis_details, dict) else {}
    recommendation = details.get("ai_recommendation") if analyzed else None
    return {
        "id": application.id,
        "name": application.name,
        "email": application.email,
        "job_id": job.id,
        "position": job.position,
        "company_name": job.company_name,
        "owner_id": job.owner_id,
        "owner_email": owner_email,
        "owner_name": owner_name,
        "application_status": application.application_status,
        "analysis_status": application.analysis_status,
        "ai_score": application.ai_score if analyzed else None,
        "ai_recommendation": str(recommendation) if recommendation else None,
        "hiring_status": application.hiring_status,
        "interview_status": application.interview_status,
        "is_candidate": application.is_candidate,
        "candidate_at": application.candidate_at,
        "submitted_at": application.submitted_at,
    }


def list_applications(
    db: Session, filters: ApplicationFilters, *, page: int, limit: int, sort: str, order: str
) -> schemas.AdminApplicationPage:
    rows, total = admin_crud.list_applications(db, filters, page=page, limit=limit, sort=sort, order=order)
    return schemas.AdminApplicationPage(
        items=[schemas.AdminApplicationRow(**_application_row(*row)) for row in rows],
        total=total,
        page=page,
        limit=limit,
        summary=schemas.ApplicationSummary(**admin_crud.application_summary(db, filters.candidates_only)),
    )


def get_application_detail(db: Session, application_id: int) -> schemas.AdminApplicationDetail | None:
    """Full application view for admins.

    The resume file itself is *not* served to admins (only whether one
    exists): CVs stay reachable solely by the owning HR user, as before.
    """
    application = application_crud.get_application(db, application_id)
    if application is None:
        return None
    owner = db.execute(select(User).where(User.id == application.job.owner_id)).scalar_one()
    raw_answers = (application.application_response.responses if application.application_response else None) or []
    return schemas.AdminApplicationDetail(
        **_application_row(application, application.job, owner.email, owner.full_name),
        analysis_error=application.analysis_error,
        analysis=stored_analysis(application),
        responses=[
            ApplicantAnswer(
                field_id=str(answer.get("field_id") or answer.get("id") or ""),
                key=str(answer.get("key") or ""),
                label=str(answer.get("label") or ""),
                type=str(answer.get("type") or ""),
                # File answers hold storage paths; admins only see that a file exists.
                value="(file)" if answer.get("type") == "file" else answer.get("value"),
            )
            for answer in raw_answers
            if isinstance(answer, dict)
        ],
        interviews=[ApplicationInterviewSummary.model_validate(item) for item in application.interviews or []],
        has_resume=bool(application.resume_path),
    )


# ---------------------------------------------------------------------------
# Interviews
# ---------------------------------------------------------------------------


def list_interviews(db: Session, *, page: int, limit: int, **filters: Any) -> schemas.AdminInterviewPage:
    rows, total = admin_crud.list_interviews(db, page=page, limit=limit, **filters)
    summary = admin_crud.interview_summary(db, datetime.now(timezone.utc))
    progress = admin_crud.application_summary(db, candidates_only=True)["interview_status"]
    return schemas.AdminInterviewPage(
        items=[
            schemas.AdminInterviewRow(
                id=interview.id,
                candidate_id=application.id,
                candidate_name=application.name,
                job_id=job.id,
                position=job.position,
                company_name=job.company_name,
                hr_id=interview.hr_id,
                hr_email=hr_email,
                hr_name=hr_name,
                interviewer=interview.interviewer,
                scheduled_at=interview.scheduled_at,
                duration_minutes=interview.duration_minutes,
                status=interview.status,
                created_at=interview.created_at,
            )
            for interview, application, job, hr_email, hr_name in rows
        ],
        total=total,
        page=page,
        limit=limit,
        summary=schemas.InterviewSummary(**summary, candidate_progress=progress),
    )
