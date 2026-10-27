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


def create(
    db: Session,
    *,
    email: str,
    full_name: str,
    password: str,
    phone: str | None,
    is_email_verified: bool = False,
) -> CandidateAccount:
    """Insert a new account with a bcrypt-hashed password.

    ``is_email_verified`` defaults to False: the public candidate registration
    path creates unverified accounts. Programmatic/tests can pass True.
    """
    account = CandidateAccount(
        email=email.strip().lower(),
        full_name=full_name.strip(),
        phone=phone,
        hashed_password=hash_password(password),
        is_email_verified=is_email_verified,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def get_by_google_id(db: Session, google_id: str) -> CandidateAccount | None:
    """Return the candidate linked to the given Google account id, or ``None``."""
    return db.query(CandidateAccount).filter(CandidateAccount.google_id == google_id).first()


def _link_and_refresh_google_candidate_profile(
    db: Session,
    candidate: CandidateAccount,
    google_id: str,
    full_name: str,
    picture: str | None,
) -> None:
    """Attach the Google identity and refresh profile columns when changed."""
    changed = False
    if candidate.google_id is None:
        candidate.google_id = google_id
        changed = True
    # A verified Google address satisfies the email-verification gate.
    if not candidate.is_email_verified:
        candidate.is_email_verified = True
        candidate.email_verification_issued_at = None
        changed = True
    if full_name and candidate.full_name != full_name:
        candidate.full_name = full_name
        changed = True
    if picture and candidate.picture != picture:
        candidate.picture = picture
        changed = True
    if changed:
        db.commit()
        db.refresh(candidate)


def get_or_create_google_candidate(
    db: Session,
    *,
    google_id: str,
    email: str,
    full_name: str,
    picture: str | None,
) -> CandidateAccount:
    """Resolve (find or create) a candidate authenticated via Google."""
    email = email.strip().lower()
    full_name = full_name.strip()
    candidate = get_by_google_id(db, google_id)
    if candidate is None:
        candidate = get_by_email(db, email)

    if candidate is not None:
        _link_and_refresh_google_candidate_profile(db, candidate, google_id, full_name, picture)
        return candidate

    candidate = CandidateAccount(
        email=email,
        full_name=full_name,
        picture=picture,
        google_id=google_id,
        is_active=True,
        # Google verified this address (caller checks the email_verified claim).
        is_email_verified=True,
    )
    db.add(candidate)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        candidate = get_by_google_id(db, google_id) or get_by_email(db, email)
        if candidate is None:
            raise ValueError(
                "This Google email is already registered with another account."
            ) from None
        _link_and_refresh_google_candidate_profile(db, candidate, google_id, full_name, picture)
        return candidate
    db.refresh(candidate)
    return candidate


def update(db: Session, account: CandidateAccount, changes: dict[str, Any]) -> CandidateAccount:
    """Apply ``changes`` to the account and return the refreshed row."""
    for field, value in changes.items():
        setattr(account, field, value)
    db.commit()
    db.refresh(account)
    return account
