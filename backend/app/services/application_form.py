"""Application-form business logic (token, validation, public submissions).

Responsibilities:

* Generate secure public application tokens.
* Validate HR-authored field configurations (strict) and AI suggestions
  (lenient) — both end up in the same stored JSON structure.
* Build the candidate-facing payload (no private data).
* Validate submitted candidate data server-side against the stored
  configuration and persist it through the existing Worker pipeline.

The public form's layout is rendered by the frontend's fixed template; this
module only ever deals with *data*.
"""

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.crud import application_form as application_form_crud
from app.crud import application_response as application_response_crud
from app.crud import worker as worker_crud
from app.models.application_form import ApplicationForm
from app.models.job import Job
from app.schemas.application_form import (
    MAX_FIELDS,
    MAX_TEXT_VALUE_LENGTH,
    PublicApplicationResponse,
    PublicApplicationJobInfo,
    FormValidationError,
    generate_public_token,
    normalise_application_fields,
    slugify_key,
    validate_application_form_fields,
)
from app.schemas.worker import WorkerCreate
from app.services import job as job_service

# ---------------------------------------------------------------------------
# Exceptions (translated to HTTP responses by the routers)
# ---------------------------------------------------------------------------


class SubmissionValidationError(Exception):
    """Candidate submission failed server-side validation (HTTP 422)."""

    def __init__(self, message: str) -> None:
        self.message = message
        self.status_code = 422  # Unprocessable Content
        super().__init__(message)


class DuplicateSubmissionError(Exception):
    """The same candidate re-submitted within the cooldown window (HTTP 409)."""

    def __init__(
        self,
        message: str = "Your application was already received a moment ago.",
    ) -> None:
        self.message = message
        self.status_code = status.HTTP_409_CONFLICT
        super().__init__(message)


# ---------------------------------------------------------------------------
# File handling (resume uploads)
# ---------------------------------------------------------------------------

_RESUMES_DIR = "resumes"

#: Extension whitelist by original filename suffix (never trusted for storage
#: names — only the suffix is reused and only if it is whitelisted).
_ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt"}

#: Content types accepted for resume files (mirrors the legacy public apply
#: endpoint so the product behaves consistently).
_ALLOWED_CONTENT_TYPES = {
    "application/pdf": ".pdf",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "text/plain": ".txt",
}

MAX_RESUME_SIZE_BYTES = 10 * 1024 * 1024  # 10MB (matches legacy behaviour)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^[+0-9()\-\s.]{6,32}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_URL_RE = re.compile(r"^https?://\S+$", re.IGNORECASE)


def _resume_upload_dir() -> Path:
    return Path(settings.UPLOAD_DIR) / _RESUMES_DIR


def save_resume_file(filename: str, content_type: str, content: bytes) -> str:
    """Persist an uploaded resume under ``UPLOAD_DIR/resumes``.

    The stored name is always server-generated (``<uuid4 hex>.<safe ext>``);
    the candidate-provided filename is never used as-is. Returns the path
    relative to ``UPLOAD_DIR`` (e.g. ``resumes/<hex>.pdf``).
    """
    suffix = None
    original = Path(filename or "").suffix.lower()
    if original in _ALLOWED_EXTENSIONS:
        suffix = original
    elif (content_type or "").lower() in _ALLOWED_CONTENT_TYPES:
        suffix = _ALLOWED_CONTENT_TYPES[content_type.lower()]
    if suffix is None:
        raise SubmissionValidationError(
            "Unsupported file type. Allowed: PDF, DOC, DOCX, TXT."
        )

    directory = _resume_upload_dir()
    directory.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid4().hex}{suffix}"
    (directory / stored_name).write_bytes(content)
    return f"{_RESUMES_DIR}/{stored_name}"


# ---------------------------------------------------------------------------
# Public payload (candidate-facing)
# ---------------------------------------------------------------------------


def build_public_payload(job: Job, form: ApplicationForm) -> PublicApplicationResponse:
    """Return the safe, candidate-facing application payload.

    Only job presentation fields and the field configuration are included —
    never owner ids, leads counts, AI prompts or internal bookkeeping.
    """
    return PublicApplicationResponse(
        job=PublicApplicationJobInfo(
            company_name=job.company_name,
            position=job.position,
            description=job.description or "",
            required_skills=job.required_skills or "",
            required_experience=job.required_experience or "",
        ),
        fields=sorted(
            form.fields, key=lambda field: field.get("order", 0)
        ),
    )


# ---------------------------------------------------------------------------
# Form configuration persistence (HR-facing)
# ---------------------------------------------------------------------------


def create_form_for_job(
    db: Session, job: Job, raw_fields: Any
) -> ApplicationForm:
    """Validate HR fields and create the job's form config + public token."""
    fields = validate_application_form_fields(raw_fields)
    return application_form_crud.create_form(
        db, job, fields, generate_public_token()
    )


def upsert_form_for_job(
    db: Session, job: Job, raw_fields: Any
) -> ApplicationForm:
    """Create or update a job's form configuration (preserving the token)."""
    fields = validate_application_form_fields(raw_fields)
    form = application_form_crud.get_form_by_job(db, job.id)
    if form is None:
        return application_form_crud.create_form(
            db, job, fields, generate_public_token()
        )
    return application_form_crud.update_fields(db, form, fields)


def publish_form(
    db: Session, form: ApplicationForm, *, regenerate_token: bool = False
) -> ApplicationForm:
    """(Re)generate the public token of an existing form configuration."""
    if regenerate_token:
        form = application_form_crud.rotate_public_token(
            db, form, generate_public_token()
        )
    return form


def default_suggestion_fields() -> list[dict[str, Any]]:
    """Starter field set used when the AI provides no usable suggestions.

    Deliberately a *data* default (not AI output): the public template renders
    exactly these definitions the same way it renders AI-suggested ones.
    """
    return normalise_application_fields(
        [
            {
                "label": "Full name",
                "type": "text",
                "required": True,
                "description": "Your first and last name.",
            },
            {
                "label": "Email",
                "type": "email",
                "required": True,
                "description": "We will contact you at this address.",
            },
            {"label": "Phone", "type": "phone", "required": False},
            {
                "label": "Resume",
                "type": "file",
                "required": True,
                "description": "PDF, DOC, DOCX or TXT (max 10MB).",
            },
            {"label": "Years of experience", "type": "number", "required": False},
            {"label": "Portfolio or LinkedIn URL", "type": "url", "required": False},
        ]
    )


# ---------------------------------------------------------------------------
# Submission validation (server-side, candidate-facing)
# ---------------------------------------------------------------------------


def _is_empty(value: Any) -> bool:
    if value is None or value is False:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    if isinstance(value, list) and len(value) == 0:
        return True
    return value == ""


def _validate_text(field: dict, value: Any) -> str:
    if not isinstance(value, str):
        raise SubmissionValidationError(f"\"{field['label']}\" must be text.")
    text = value.strip()
    if len(text) > MAX_TEXT_VALUE_LENGTH:
        raise SubmissionValidationError(f"\"{field['label']}\" is too long.")
    return text


def _validate_number(field: dict, value: Any) -> str:
    if isinstance(value, bool) or isinstance(value, (dict, list)):
        raise SubmissionValidationError(f"\"{field['label']}\" must be a number.")
    text = str(value).strip()
    if len(text) > 30:
        raise SubmissionValidationError(f"\"{field['label']}\" is not a valid number.")
    try:
        float(text)
    except ValueError:
        raise SubmissionValidationError(  # noqa: TRY200/B904 — candidate-safe message
            f"\"{field['label']}\" must be a valid number."
        ) from None
    return text


def _validate_file_input(
    field: dict, file_input: tuple[str, str, bytes] | None
) -> tuple[str, str, bytes] | None:
    """Validate an uploaded file for a ``file`` field.

    ``file_input`` is ``(filename, content_type, content)`` or ``None``.
    """
    if file_input is None:
        return None
    filename, content_type, content = file_input
    suffix = Path(filename or "").suffix.lower()
    type_ok = suffix in _ALLOWED_EXTENSIONS or (
        content_type or "").lower() in _ALLOWED_CONTENT_TYPES
    if not type_ok:
        raise SubmissionValidationError(
            f"\"{field['label']}\": unsupported file type. Allowed: PDF, DOC, DOCX, TXT."
        )
    if len(content) > MAX_RESUME_SIZE_BYTES:
        raise SubmissionValidationError(
            f"\"{field['label']}\": file exceeds the 10MB size limit."
        )
    return file_input


def _is_valid_date(text: str) -> bool:
    try:
        datetime.strptime(text, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def _validate_field_value(
    field: dict, value: Any, files: dict[str, tuple[str, str, bytes]]
) -> Any:
    """Validate and normalise one submitted value against its field config.

    Raises ``SubmissionValidationError`` with a candidate-safe message.
    """
    field_type = field.get("type")
    label = field.get("label", "This question")

    if field_type == "file":
        return _validate_file_input(field, files.get(field["id"]))

    if field_type == "checkbox":
        if value is True or value == "true":
            return True
        if value is False or value is None or value == "" or value == "false":
            return False
        raise SubmissionValidationError(f"\"{label}\" must be a checkbox value.")

    if field_type == "multi_select":
        if _is_empty(value):
            return []
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise SubmissionValidationError(f"\"{label}\" must be a list of options.")
        selected = {str(v) for v in value}
        allowed = set(field.get("options") or [])
        if not selected.issubset(allowed):
            raise SubmissionValidationError(
                f"\"{label}\" contains an option that is not available."
            )
        # Preserve the field's option order for a stable stored record.
        return [option for option in field.get("options") or [] if option in selected]

    if field_type == "select":
        if _is_empty(value):
            return ""
        if not isinstance(value, str) or value not in (field.get("options") or []):
            raise SubmissionValidationError(
                f"\"{label}\" must be one of the available options."
            )
        return value

    # All remaining types are string-based.
    if _is_empty(value):
        return ""
    if isinstance(value, (dict, list, bool)):
        raise SubmissionValidationError(f"\"{label}\" has an invalid value.")
    if not isinstance(value, str):
        value = str(value)

    if field_type == "email":
        text = _validate_text(field, value)
        if text and not _EMAIL_RE.match(text):
            raise SubmissionValidationError(
                f"\"{label}\" must be a valid email address."
            )
        return text.lower()
    if field_type == "phone":
        text = _validate_text(field, value)
        if text and not _PHONE_RE.match(text):
            raise SubmissionValidationError(f"\"{label}\" must be a valid phone number.")
        return text
    if field_type == "number":
        return _validate_number(field, value)
    if field_type == "date":
        text = _validate_text(field, value)
        if text and (not _DATE_RE.match(text) or not _is_valid_date(text)):
            raise SubmissionValidationError(
                f"\"{label}\" must be a valid date (YYYY-MM-DD)."
            )
        return text
    if field_type == "url":
        text = _validate_text(field, value)
        if text and not _URL_RE.match(text):
            raise SubmissionValidationError(
                f"\"{label}\" must be a URL starting with http:// or https://."
            )
        return text

    # text / textarea / fallback
    return _validate_text(field, value)


def validate_submission_values(
    fields: list[dict], raw_values: Any, files: dict[str, tuple[str, str, bytes]]
) -> dict[str, Any]:
    """Validate a candidate submission against the stored configuration.

    Args:
        fields: The stored field definitions for the job's application form.
        raw_values: Parsed JSON object mapping field id -> submitted value.
        files: Mapping field id -> ``(filename, content_type, content)``.

    Returns:
        Normalised values keyed by field id (files are validated here and
        persisted later, keyed by field id as well).

    Raises:
        SubmissionValidationError: On any rule violation. The message is
            candidate-safe (no internals).
    """
    if not isinstance(raw_values, dict):
        raise SubmissionValidationError("Invalid application data submitted.")

    field_ids = {field["id"] for field in fields}
    if any(key not in field_ids for key in raw_values.keys()):
        raise SubmissionValidationError(
            "Your application contains questions that are not part of this "
            "form. Please reload the page and try again."
        )

    values: dict[str, Any] = {}
    missing_required: list[str] = []
    for field in sorted(fields, key=lambda f: f.get("order", 0)):
        value = _validate_field_value(field, raw_values.get(field["id"]), files)
        values[field["id"]] = value
        if field.get("required") and _is_empty(value):
            if field.get("type") == "checkbox":
                raise SubmissionValidationError(
                    f"\"{field['label']}\" must be checked."
                )
            missing_required.append(field["label"])
        if field.get("type") == "file" and field.get("required") and value is None:
            missing_required.append(field["label"])

    if missing_required:
        raise SubmissionValidationError(
            f"Please complete the required fields: {', '.join(missing_required)}."
        )

    return values


# ---------------------------------------------------------------------------
# Candidate identity mapping (Worker record integration)
# ---------------------------------------------------------------------------

_NAME_KEYS = ("full_name", "name", "first_name")
_EMAIL_KEYS = ("email", "email_address")


def extract_candidate_identity(
    fields: list[dict], values: dict[str, Any]
) -> tuple[str, str]:
    """Map submitted values to the Worker record's name/email.

    Matches canonical keys first (``full_name``/``name``, ``email``), then
    falls back to a key/label search. When the HR-authored form has neither a
    name nor an email question, safe fallbacks keep the existing candidate
    pipeline working (those columns are NOT NULL).
    """
    by_key = {field.get("key", ""): field for field in fields}

    name = ""
    for key in _NAME_KEYS:
        field = by_key.get(key)
        if field and values.get(field["id"]):
            name = str(values[field["id"]])
            break
    if not name:
        for field in fields:
            haystack = f"{field.get('key', '')} {field.get('label', '')}".lower()
            if "name" in haystack and field.get("type") in ("text", "textarea"):
                value = values.get(field["id"])
                if value:
                    name = str(value)
                    break

    email = ""
    for key in _EMAIL_KEYS:
        field = by_key.get(key)
        if field and values.get(field["id"]):
            candidate = str(values[field["id"]])
            if _EMAIL_RE.match(candidate):
                email = candidate
                break
    if not email:
        for field in fields:
            haystack = f"{field.get('key', '')} {field.get('label', '')}".lower()
            value = values.get(field["id"])
            if "email" in haystack and isinstance(value, str) and _EMAIL_RE.match(value):
                email = value
                break

    safe_name = (name or "Anonymous candidate").strip()[:255]
    safe_email = (
        email or f"anonymous+{uuid4().hex[:8]}@candidates.local"
    ).strip().lower()[:255]
    return safe_name, safe_email


# ---------------------------------------------------------------------------
# Submission persistence
# ---------------------------------------------------------------------------


def _has_recent_submission(
    db: Session, job_id: int, email: str, window_seconds: int = 60
) -> bool:
    """Guard against accidental duplicate submissions (same job + email)."""
    from app.models.worker import Worker

    cutoff = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
    recent = (
        db.query(Worker.id)
        .filter(
            Worker.job_id == job_id,
            Worker.email == email,
            Worker.submitted_at >= cutoff,
        )
        .first()
    )
    return recent is not None


def _build_response_snapshot(
    fields: list[dict], values: dict[str, Any], stored_files: dict[str, str]
) -> list[dict[str, Any]]:
    """Snapshot the answers (field metadata + value) for durable storage."""
    snapshot: list[dict[str, Any]] = []
    for field in sorted(fields, key=lambda f: f.get("order", 0)):
        if field.get("type") == "file":
            value: Any = stored_files.get(field["id"], "")
        else:
            value = values.get(field["id"], "")
        snapshot.append(
            {
                "field_id": field["id"],
                "key": field.get("key", ""),
                "label": field.get("label", ""),
                "type": field.get("type", ""),
                "value": value,
            }
        )
    return snapshot


def submit_public_application(
    db: Session,
    job: Job,
    form: ApplicationForm,
    raw_values: Any,
    files: dict[str, tuple[str, str, bytes]],
) -> int:
    """Validate and persist a public application submission.

    Returns the created worker/candidate id. Reuses the existing Worker
    pipeline (name/email/resume_path/hiring status) and stores the structured
    answers next to it, so the HR candidate flow keeps working unchanged.
    """
    fields = form.fields or []
    if not fields:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This application link is no longer available.",
        )

    values = validate_submission_values(fields, raw_values, files)

    # Persist files (type/size were already whitelisted during validation).
    stored_files: dict[str, str] = {}
    resume_path = ""
    for field in sorted(fields, key=lambda f: f.get("order", 0)):
        if field.get("type") != "file":
            continue
        file_input = files.get(field["id"])
        if file_input is None:
            continue
        filename, content_type, content = file_input
        path = save_resume_file(filename, content_type, content)
        stored_files[field["id"]] = path
        if not resume_path:
            resume_path = path

    name, email = extract_candidate_identity(fields, values)
    if _has_recent_submission(db, job.id, email):
        raise DuplicateSubmissionError()

    worker = worker_crud.create_worker(
        db, job.id, WorkerCreate(name=name, email=email, resume_path=resume_path)
    )
    application_response_crud.create_response(
        db, worker.id, _build_response_snapshot(fields, values, stored_files)
    )
    job_service.increment_leads_count(db, job.id)
    return worker.id
