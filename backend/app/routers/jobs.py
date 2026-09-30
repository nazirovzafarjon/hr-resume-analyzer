"""Job CRUD API endpoints.

An HR user manages their own jobs; an admin session manages every HR user's
jobs through the same endpoints (see ``dependencies.auth.AccessScope``).
Another user's job looks exactly like a missing one (404) to a regular HR user.
"""

import math
import time

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.crud import job as job_crud
from app.crud import application_form as application_form_crud
from app.dependencies.audit import get_audit_context
from app.dependencies.auth import AccessScope, get_access_scope
from app.models.job import Job
from app.schemas.application_form import (
    ApplicationFormPublishRequest,
    ApplicationFormResponse,
    ApplicationFormPayload,
    FormValidationError,
)
from app.schemas.job import (
    JobAIAnalysisResult,
    JobAnalyzeRequest,
    JobCreate,
    JobResponse,
    JobUpdate,
)
from app.services.ai import monitoring as ai_monitoring
from app.services.ai import provider as ai_provider_service
from app.services import application_form as application_form_service
from app.services import audit
from app.services.audit import AuditAction, AuditContext, AuditResource
from app.services.ai.job_analyzer import (
    AIProviderAuthError,
    AIProviderUnavailableError,
    AIServiceError,
    AIRateLimitError,
    analyze_vacancy,
    close_ai_client,
)


router = APIRouter()


def _get_owned_job(db: Session, job_id: int, scope: AccessScope) -> Job:
    """Return the job if it is in the caller's scope, else raise 404."""
    job = job_crud.get_job(db, job_id)
    if job is None or not scope.can_access(job.owner_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


def _get_owned_application_form(db: Session, job_id: int, scope: AccessScope):
    """Return the job's application form (owner or admin) or raise 404."""
    job = _get_owned_job(db, job_id, scope)
    form = application_form_crud.get_form_by_job(db, job.id)
    if form is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No application form configured for this job yet.",
        )
    return job, form


@router.get("", response_model=list[JobResponse])
def list_jobs(
    db: Session = Depends(get_db),
    scope: AccessScope = Depends(get_access_scope),
) -> list[Job]:
    """Return the caller's jobs (every HR user's jobs in an admin session)."""
    return job_crud.get_jobs_for_user(db, scope.owner_id)


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def create_job(
    payload: JobCreate,
    db: Session = Depends(get_db),
    scope: AccessScope = Depends(get_access_scope),
    audit_ctx: AuditContext = Depends(get_audit_context),
) -> Job:
    """Create a new job owned by the caller (an admin creates it as their own).

    When ``payload.application_form`` is provided (the "Generate Public
    Application Link" step of the create flow), the reviewed fields are
    validated, stored and a public token is generated atomically with the
    job. Invalid form data fails the whole request (HTTP 422) so no job is
    created without its reviewed form.
    """
    job = job_crud.create_job(db, scope.user.id, payload)
    if payload.application_form is not None:
        try:
            application_form_service.create_form_for_job(
                db, job, payload.application_form.model_dump()["fields"]
            )
        except FormValidationError as exc:
            # ``create_job`` already committed, so remove the job again to
            # keep job + form creation atomic: a failed publish must not
            # leave a job without its reviewed form behind.
            job_crud.delete_job(db, job.id)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.message
            ) from exc
    db.refresh(job)
    audit.record(
        db,
        AuditAction.CREATE_JOB,
        resource_type=AuditResource.JOB,
        resource_id=job.id,
        actor=scope.user,
        details={"position": job.position, "company": job.company_name},
        context=audit_ctx,
    )
    return job


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    scope: AccessScope = Depends(get_access_scope),
) -> Job:
    """Return a single job in the caller's scope."""
    return _get_owned_job(db, job_id, scope)


@router.put("/{job_id}", response_model=JobResponse)
def update_job(
    job_id: int,
    payload: JobUpdate,
    db: Session = Depends(get_db),
    scope: AccessScope = Depends(get_access_scope),
    audit_ctx: AuditContext = Depends(get_audit_context),
) -> Job:
    """Update a job in the caller's scope."""
    job = _get_owned_job(db, job_id, scope)
    job = job_crud.update_job(db, job, payload)
    audit.record(
        db,
        AuditAction.UPDATE_JOB,
        resource_type=AuditResource.JOB,
        resource_id=job.id,
        actor=scope.user,
        details={"fields": audit.changed_fields(payload)},
        context=audit_ctx,
    )
    return job


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(
    job_id: int,
    db: Session = Depends(get_db),
    scope: AccessScope = Depends(get_access_scope),
    audit_ctx: AuditContext = Depends(get_audit_context),
) -> None:
    """Delete a job in the caller's scope."""
    job = _get_owned_job(db, job_id, scope)
    details = {"position": job.position, "company": job.company_name}
    job_crud.delete_job(db, job_id)
    audit.record(
        db,
        AuditAction.DELETE_JOB,
        resource_type=AuditResource.JOB,
        resource_id=job_id,
        actor=scope.user,
        details=details,
        context=audit_ctx,
    )
    return None


# ---------------------------------------------------------------------------
# Application form configuration (public application link management)
# ---------------------------------------------------------------------------


@router.get("/{job_id}/application-form", response_model=ApplicationFormResponse)
def get_application_form(
    job_id: int,
    db: Session = Depends(get_db),
    scope: AccessScope = Depends(get_access_scope),
) -> ApplicationFormResponse:
    """Return the job's application form configuration (owner or admin)."""
    _job, form = _get_owned_application_form(db, job_id, scope)
    return form


@router.put("/{job_id}/application-form", response_model=ApplicationFormResponse)
def save_application_form(
    job_id: int,
    payload: ApplicationFormPayload,
    db: Session = Depends(get_db),
    scope: AccessScope = Depends(get_access_scope),
) -> ApplicationFormResponse:
    """Create or update the job's application form configuration.

    Updating the fields never rotates the public token, so existing shared
    links keep working — HR's customised form is preserved unless the token
    is explicitly regenerated via the publish endpoint.
    """
    job = _get_owned_job(db, job_id, scope)
    try:
        form = application_form_service.upsert_form_for_job(db, job, payload.fields)
    except FormValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.message
        ) from exc
    return form


@router.post(
    "/{job_id}/application-form/publish", response_model=ApplicationFormResponse
)
def publish_application_form(
    job_id: int,
    payload: ApplicationFormPublishRequest | None = None,
    db: Session = Depends(get_db),
    scope: AccessScope = Depends(get_access_scope),
) -> ApplicationFormResponse:
    """(Re)generate the public token for the job's application form.

    With ``regenerate_token`` the old link stops working (used when a link
    was shared too widely); without it the existing token is returned as-is.
    """
    _job, form = _get_owned_application_form(db, job_id, scope)
    regenerate = bool(payload.regenerate_token) if payload is not None else False
    return application_form_service.publish_form(
        db, form, regenerate_token=regenerate
    )


@router.delete("/{job_id}/application-form", status_code=status.HTTP_204_NO_CONTENT)
def reset_application_form(
    job_id: int,
    db: Session = Depends(get_db),
    scope: AccessScope = Depends(get_access_scope),
) -> None:
    """Remove the job's application form configuration (explicit reset).

    Existing candidates and their stored answers are preserved; only the
    form configuration and its public link are removed.
    """
    _job, form = _get_owned_application_form(db, job_id, scope)
    application_form_crud.delete_form(db, form)
    return None


@router.post("/analyze", response_model=JobAIAnalysisResult)
async def analyze_job(
    payload: JobAnalyzeRequest,
    db: Session = Depends(get_db),
    scope: AccessScope = Depends(get_access_scope),
) -> JobAIAnalysisResult:
    """Analyze a vacancy using AI and return structured job information.

    The AI extracts company name, position, description, required skills,
    and required experience from the provided vacancy text.

    This endpoint does not create a job - it only returns the AI analysis
    for the user to review and optionally use when creating a job.
    """
    cfg: dict = {}
    started = time.monotonic()

    def record(error: AIServiceError | None = None) -> None:
        ai_monitoring.record_run(
            db,
            kind=ai_monitoring.KIND_VACANCY,
            cfg=cfg,
            duration_ms=round((time.monotonic() - started) * 1000),
            owner_id=scope.user.id,
            error=error,
        )

    try:
        # The user's own provider when configured, else the platform's.
        cfg = ai_provider_service.resolve_for_user(db, scope.user.id)
        result = await analyze_vacancy(payload.content, cfg=cfg)
    except AIServiceError as exc:
        # Neither a rejected vacancy text (422) nor missing AI configuration
        # reached a provider, so neither is an AI attempt worth monitoring.
        if exc.status_code != status.HTTP_422_UNPROCESSABLE_ENTITY and not isinstance(
            exc, ai_provider_service.AIConfigurationRequiredError
        ):
            record(exc)
        exc = ai_provider_service.safe_error_for(cfg, exc)
        headers = None
        if isinstance(exc, AIRateLimitError) and exc.retry_after:
            headers = {"Retry-After": str(math.ceil(exc.retry_after))}
        raise HTTPException(status_code=exc.status_code, detail=exc.message, headers=headers)
    record()
    return result