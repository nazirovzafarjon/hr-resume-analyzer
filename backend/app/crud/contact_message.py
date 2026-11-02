"""CRUD operations for Contact Us messages.

Contains only database access. Business logic belongs in services.
"""

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.contact_message import ContactMessage
from app.schemas.contact_message import ContactMessageCreate


def create_contact_message(db: Session, payload: ContactMessageCreate) -> ContactMessage:
    """Store and return a new contact message."""
    data = payload.model_dump()
    data["is_read"] = False
    contact_message = ContactMessage(**data)
    db.add(contact_message)
    db.commit()
    db.refresh(contact_message)
    return contact_message


def get_contact_messages(
    db: Session,
    page: int = 1,
    limit: int = 25,
    is_read: bool | None = None,
    q: str | None = None,
) -> tuple[list[ContactMessage], int, int]:
    """Return paginated contact inquiries, total matching count, and overall unread count."""
    unread_count = (
        db.query(func.count(ContactMessage.id))
        .filter(ContactMessage.is_read.is_(False))
        .scalar()
        or 0
    )

    query = db.query(ContactMessage)
    if is_read is not None:
        query = query.filter(ContactMessage.is_read.is_(is_read))

    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(
            or_(
                ContactMessage.first_name.ilike(term),
                ContactMessage.last_name.ilike(term),
                ContactMessage.email.ilike(term),
                ContactMessage.subject.ilike(term),
                ContactMessage.message.ilike(term),
            )
        )

    total = query.count()
    items = (
        query.order_by(ContactMessage.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return items, total, unread_count


def get_contact_message(db: Session, message_id: int) -> ContactMessage | None:
    """Find a contact message by ID."""
    return db.query(ContactMessage).filter(ContactMessage.id == message_id).first()


def mark_contact_message_read(
    db: Session, message_id: int, is_read: bool = True
) -> ContactMessage | None:
    """Update is_read status for a contact message."""
    message = get_contact_message(db, message_id)
    if not message:
        return None
    message.is_read = is_read
    db.commit()
    db.refresh(message)
    return message


def delete_contact_message(db: Session, message_id: int) -> bool:
    """Delete a contact message by ID."""
    message = get_contact_message(db, message_id)
    if not message:
        return False
    db.delete(message)
    db.commit()
    return True


def get_unread_count(db: Session) -> int:
    """Return total count of unread contact messages."""
    return (
        db.query(func.count(ContactMessage.id))
        .filter(ContactMessage.is_read.is_(False))
        .scalar()
        or 0
    )
