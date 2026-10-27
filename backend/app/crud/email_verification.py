"""CRUD operations for emailed verification codes.

Plain database access only — code generation, hashing, expiry and rate-limit
rules live in ``app.services.email_verification``.
"""

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.email_verification import EmailVerification


def create(
    db: Session,
    *,
    user_id: int,
    code_hash: str,
    expires_at: datetime,
) -> EmailVerification:
    """Insert a new active verification code for a user."""
    record = EmailVerification(
        user_id=user_id,
        code_hash=code_hash,
        expires_at=expires_at,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_latest_active(db: Session, user_id: int) -> EmailVerification | None:
    """Return the newest not-yet-used code for a user, or ``None``."""
    return (
        db.query(EmailVerification)
        .filter(
            EmailVerification.user_id == user_id,
            EmailVerification.used_at.is_(None),
        )
        .order_by(EmailVerification.id.desc())
        .first()
    )


def invalidate_active(db: Session, user_id: int, when: datetime) -> int:
    """Mark every unused code for a user as used; returns how many were closed."""
    updated = (
        db.query(EmailVerification)
        .filter(
            EmailVerification.user_id == user_id,
            EmailVerification.used_at.is_(None),
        )
        .update({EmailVerification.used_at: when}, synchronize_session=False)
    )
    db.commit()
    return updated


def save(db: Session, record: EmailVerification, changes: dict) -> EmailVerification:
    """Apply ``changes`` to a verification record and return it refreshed."""
    for field, value in changes.items():
        setattr(record, field, value)
    db.commit()
    db.refresh(record)
    return record
