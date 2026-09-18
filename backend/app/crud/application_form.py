"""CRUD operations for application-form configuration.

Contains only database access. Business logic (validation, token rules,
submission handling) belongs in services.
"""

from sqlalchemy.orm import Session

from app.models.application_form import ApplicationForm
from app.models.job import Job


def get_form_by_job(db: Session, job_id: int) -> ApplicationForm | None:
    """Return the application form configured for a job, or ``None``."""
    return db.query(ApplicationForm).filter(ApplicationForm.job_id == job_id).first()


def get_form_by_token(db: Session, token: str) -> ApplicationForm | None:
    """Return the application form matching a public token, or ``None``."""
    if not token or len(token) > 64:
        return None
    return (
        db.query(ApplicationForm)
        .filter(ApplicationForm.public_token == token)
        .first()
    )


def create_form(
    db: Session, job: Job, fields: list[dict], public_token: str
) -> ApplicationForm:
    """Create the application form for a job (one per job)."""
    form = ApplicationForm(job_id=job.id, fields=fields, public_token=public_token)
    db.add(form)
    db.commit()
    db.refresh(form)
    return form


def update_fields(db: Session, form: ApplicationForm, fields: list[dict]) -> ApplicationForm:
    """Replace the stored field configuration, keeping the public token."""
    form.fields = fields
    db.commit()
    db.refresh(form)
    return form


def rotate_public_token(db: Session, form: ApplicationForm, public_token: str) -> ApplicationForm:
    """Replace the public token (e.g. when the old link was shared too widely)."""
    form.public_token = public_token
    db.commit()
    db.refresh(form)
    return form


def delete_form(db: Session, form: ApplicationForm) -> None:
    """Delete the application-form configuration for a job."""
    db.delete(form)
    db.commit()
