"""CRUD operations for Candidate Portal accounts.

Contains only database access. Business logic lives in
``services.candidate_auth`` / ``services.candidate_portal``.
"""

from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.candidate_account import CandidateAccount


def get_by_id(db: Session, candidate_id: int) -> CandidateAccount | None:
    """Return the account with the given id, or ``None``."""
    return db.get(CandidateAccount, candidate_id)


def get_by_email(db: Session, email: str) -> CandidateAccount | None:
    """Return the account registered with ``email`` (case-insensitive), or ``None``."""
    return (
        db.query(CandidateAccount)
        .filter(func.lower(CandidateAccount.email) == email.strip().lower())
        .first()
    )


def create(db: Session, *, email: str, full_name: str, password: str, phone: str | None) -> CandidateAccount:
    """Insert a new account with a bcrypt-hashed password."""
    account = CandidateAccount(
        email=email.strip().lower(),
        full_name=full_name.strip(),
        phone=phone,
        hashed_password=hash_password(password),
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def update(db: Session, account: CandidateAccount, changes: dict[str, Any]) -> CandidateAccount:
    """Apply ``changes`` to the account and return the refreshed row."""
    for field, value in changes.items():
        setattr(account, field, value)
    db.commit()
    db.refresh(account)
    return account
