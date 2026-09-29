"""CRUD operations for Contact Us messages.

Contains only database access. Business logic belongs in services.
"""

from sqlalchemy.orm import Session

from app.models.contact_message import ContactMessage
from app.schemas.contact_message import ContactMessageCreate


def create_contact_message(db: Session, payload: ContactMessageCreate) -> ContactMessage:
    """Store and return a new contact message."""
    contact_message = ContactMessage(**payload.model_dump())
    db.add(contact_message)
    db.commit()
    db.refresh(contact_message)
    return contact_message
