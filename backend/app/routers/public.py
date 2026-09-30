"""Public API endpoints (no authentication required): candidate applications
and the landing page's Contact Us form."""

import json
import re
import uuid
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile as StarletteUploadFile

from app.core.database import get_db
from app.crud import job as job_crud
from app.crud import worker as worker_crud
from app.crud import application_form as application_form_crud
from app.models.job import Job
from app.schemas.application_form import PublicApplicationResponse, PublicSubmissionResult
from app.schemas.contact_message import ContactMessageCreate, ContactMessageResult
from app.schemas.job import PublicJobSummary
from app.schemas.worker import WorkerResponse
from app.services import application_form as application_form_service
from app.services import audit
from app.services import contact_message as contact_message_service
from app.services import job as job_service

router = APIRouter(prefix="/public", tags=["public"])

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Candidate-safe messages (never expose internal errors publicly).
_LINK_UNAVAILABLE = "This application link is no longer available."


@router.get(
    "/jobs/{job_id}",
    response_model=PublicJobSummary,
)
def public_get_job(
    job_id: str,
    db: Session = Depends(get_db),
) -> PublicJobSummary:
    """Get job presentation fields for a public application page (no auth).

    Legacy lookup (superseded by the token-based ``/public/applications/{token}``
    flow). Returns only presentation fields — never ``leads_count`` or the
    application form (which carries its secret ``public_token``): this
    endpoint accepts a guessable integer id, so nothing sensitive can ride
    along with it.
    """
    job: Job | None = None
    try:
        job_uuid = uuid.UUID(job_id)
        job = job_crud.get_job_by_public_id(db, job_uuid)
    except ValueError:
        try:
            job = job_crud.get_job(db, int(job_id))
        except ValueError:
            pass

    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    return job


@router.post(
    "/apply/{job_id}",
    response_model=WorkerResponse,
    status_code=status.HTTP_201_CREATED,
)
async def public_apply(
    job_id: str,
    name: str = Form(..., min_length=1, max_length=255),
    email: str = Form(..., max_length=255),
    resume: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> WorkerResponse:
    """Submit a candidate application for a job (public endpoint, no auth).

    Accepts multipart/form-data with:
    - name: Candidate's full name
    - email: Candidate's email
    - resume: Resume/CV file (PDF, DOC, DOCX, TXT)

    Increments the job's leads_count automatically.
    """
    # Validate email format
    if not EMAIL_REGEX.match(email):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid email format",
        )

    # Validate file type
    allowed_types = {
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
    }
    if resume.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Allowed: PDF, DOC, DOCX, TXT",
        )

    # Read file content
    file_content = await resume.read()
    if len(file_content) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds 10MB limit",
        )

    # Find job by public_id (UUID) or fall back to numeric id for backward compat
    job: Job | None = None
    try:
        job_uuid = uuid.UUID(job_id)
        job = job_crud.get_job_by_public_id(db, job_uuid)
    except ValueError:
        # Not a valid UUID, try numeric id
        try:
            job = job_crud.get_job(db, int(job_id))
        except ValueError:
            pass

    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    # Create worker/candidate record
    from app.schemas.worker import WorkerCreate

    worker = worker_crud.create_worker(
        db,
        job.id,
        WorkerCreate(name=name, email=email, resume_path=resume.filename or ""),
    )

    # Increment job leads count
    job_service.increment_leads_count(db, job.id)
    _audit_received(db, worker.id, job)

    return worker


def _audit_received(db: Session, worker_id: int, job: Job) -> None:
    """Audit an incoming public application.

    There is no actor (the applicant has no account) and deliberately no IP /
    user agent: the applicant is a private person, not a platform user.
    """
    audit.record(
        db,
        audit.AuditAction.APPLICATION_RECEIVED,
        resource_type=audit.AuditResource.APPLICATION,
        resource_id=worker_id,
        details={"job_id": job.id, "owner_id": job.owner_id},
    )


# ---------------------------------------------------------------------------
# Public application-form endpoints (fixed template, token-based)
# ---------------------------------------------------------------------------


def _get_form_with_job(db: Session, token: str):
    """Resolve a public token to its application form + job, or 404."""
    form = application_form_crud.get_form_by_token(db, token)
    if form is None or form.job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=_LINK_UNAVAILABLE
        )
    return form, form.job


@router.get(
    "/applications/{token}",
    response_model=PublicApplicationResponse,
)
def public_get_application(token: str, db: Session = Depends(get_db)):
    """Return the public application page data (no auth).

    Serves only the job presentation fields and the reviewed application
    field configuration — never owner information, internal ids, analytics
    or AI configuration.
    """
    form, job = _get_form_with_job(db, token)
    return application_form_service.build_public_payload(job, form)


@router.post(
    "/applications/{token}/submit",
    response_model=PublicSubmissionResult,
    status_code=status.HTTP_201_CREATED,
)
async def public_submit_application(
    token: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Accept a candidate submission for a published application form.

    Multipart/form-data with:
    - ``values``: JSON string mapping field id -> submitted value
    - one file part per ``file`` field, keyed by the field's id

    The payload is fully validated server-side against the stored field
    configuration before anything is persisted. No authentication — the
    token is the credential.
    """
    form, job = _get_form_with_job(db, token)

    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" not in content_type:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid submission format.",
        )

    form_data = await request.form()

    raw_values = form_data.get("values")
    if not isinstance(raw_values, str):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid application data.",
        )
    try:
        values = json.loads(raw_values)
    except (ValueError, TypeError):
        raise HTTPException(  # noqa: TRY200/B904 — candidate-safe message
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid application data.",
        ) from None

    # Collect uploaded files keyed by field id (first part wins).
    files: dict[str, tuple[str, str, bytes]] = {}
    for key, part in form_data.multi_items():
        if not isinstance(part, StarletteUploadFile):
            continue
        if key in files:
            continue
        content = await part.read()
        files[key] = (part.filename or "", part.content_type or "", content)

    try:
        worker_id = application_form_service.submit_public_application(
            db, job, form, values, files
        )
    except application_form_service.SubmissionValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.message
        ) from exc
    except application_form_service.DuplicateSubmissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=exc.message
        ) from exc

    _audit_received(db, worker_id, job)
    return PublicSubmissionResult()


# ---------------------------------------------------------------------------
# Contact Us (landing page)
# ---------------------------------------------------------------------------


@router.post(
    "/contact",
    response_model=ContactMessageResult,
    status_code=status.HTTP_201_CREATED,
)
def public_contact(
    payload: ContactMessageCreate,
    request: Request,
    db: Session = Depends(get_db),
) -> ContactMessageResult:
    """Store a Contact Us message from the landing page (no auth).

    The body is validated by :class:`ContactMessageCreate` (required, trimmed
    names and message, a real email address); invalid input gets the usual
    422 and is never stored. Signed-in visitors use the same endpoint — no
    token is read. Database failures surface as the app-wide 503 and are
    logged server-side, never echoed to the visitor.
    """
    client_key = request.client.host if request.client else "unknown"
    try:
        contact_message_service.submit_contact_message(db, payload, client_key)
    except contact_message_service.ContactRateLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=exc.message
        ) from exc
    return ContactMessageResult()
