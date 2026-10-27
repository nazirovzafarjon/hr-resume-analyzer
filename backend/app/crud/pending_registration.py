"""Database access for pending HR registrations."""

from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.pending_registration import PendingRegistration


def get_by_email(db: Session, email: str) -> PendingRegistration | None:
    """Fetch pending registration by normalized email."""
    norm = email.strip().lower()
    return db.scalars(
        select(PendingRegistration).where(PendingRegistration.email == norm)
    ).first()


def get_by_token_hash(db: Session, token_hash: str) -> PendingRegistration | None:
    """Fetch pending registration by token hash."""
    return db.scalars(
        select(PendingRegistration).where(PendingRegistration.token_hash == token_hash)
    ).first()


def create_or_update(
    db: Session,
    *,
    email: str,
    full_name: str,
    hashed_password: str,
    token_hash: str,
    code_hash: str | None,
    expires_at: datetime,
) -> PendingRegistration:
    """Insert or update pending registration for an email (upsert on initiation)."""
    norm = email.strip().lower()
    now = datetime.now(timezone.utc)
    pending = get_by_email(db, norm)
    if pending is None:
        pending = PendingRegistration(
            email=norm,
            full_name=full_name,
            hashed_password=hashed_password,
            token_hash=token_hash,
            code_hash=code_hash,
            expires_at=expires_at,
            created_at=now,
            last_sent_at=now,
            consumed_at=None,
            attempts=0,
        )
        db.add(pending)
    else:
        pending.full_name = full_name
        pending.hashed_password = hashed_password
        pending.token_hash = token_hash
        pending.code_hash = code_hash
        pending.expires_at = expires_at
        pending.last_sent_at = now
        pending.consumed_at = None
        pending.attempts = 0

    db.commit()
    db.refresh(pending)
    return pending


def mark_consumed(db: Session, pending: PendingRegistration) -> None:
    """Mark the pending registration as consumed."""
    pending.consumed_at = datetime.now(timezone.utc)
    db.commit()


def delete_pending(db: Session, pending_id: int) -> None:
    """Delete a pending registration record."""
    db.execute(delete(PendingRegistration).where(PendingRegistration.id == pending_id))
    db.commit()


def delete_expired(db: Session, cutoff: datetime) -> int:
    """Remove expired or long-consumed pending registrations."""
    result = db.execute(
        delete(PendingRegistration).where(
            (PendingRegistration.expires_at < cutoff)
            | (
                (PendingRegistration.consumed_at.is_not(None))
                & (PendingRegistration.consumed_at < cutoff)
            )
        )
    )
    db.commit()
    return result.rowcount
