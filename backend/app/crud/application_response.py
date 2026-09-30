"""CRUD operations for structured application responses (candidate answers).

Contains only database access. Business logic belongs in services.
"""

from sqlalchemy.orm import Session

from app.models.application_form import ApplicationResponse


def create_response(
    db: Session, application_id: int, responses: list[dict]
) -> ApplicationResponse:
    """Store the structured answers snapshot for a candidate submission."""
    response = ApplicationResponse(application_id=application_id, responses=responses)
    db.add(response)
    db.commit()
    db.refresh(response)
    return response


def get_response_by_application(db: Session, application_id: int) -> ApplicationResponse | None:
    """Return the stored answers for a candidate, or ``None``."""
    return (
        db.query(ApplicationResponse)
        .filter(ApplicationResponse.application_id == application_id)
        .first()
    )
