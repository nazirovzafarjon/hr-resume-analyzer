"""Candidate Portal authentication dependency.

``get_current_candidate`` is the only way a ``/api/candidate/*`` endpoint learns
who is calling. It accepts **only** ``candidate_access`` tokens, so an HR
access token (or any refresh / reset token) is rejected here, just as the HR
guard (``dependencies.auth``) rejects candidate tokens. Every candidate query
is then scoped to the returned account's id; a ``candidate_id`` sent by the
client is never used for authorization.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import TOKEN_PURPOSE_CANDIDATE_ACCESS, decode_token_for_purpose
from app.core.token_registry import is_token_revoked
from app.crud import candidate_account as candidate_crud
from app.models.candidate_account import CandidateAccount
from app.services.candidate_auth import token_predates_password_change

_bearer_scheme = HTTPBearer(auto_error=False)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or expired token",
    headers={"WWW-Authenticate": "Bearer"},
)


def candidate_from_token(db: Session, token: str) -> CandidateAccount:
    """Resolve an active candidate from a ``candidate_access`` token, else 401."""
    try:
        payload = decode_token_for_purpose(token, TOKEN_PURPOSE_CANDIDATE_ACCESS)
        candidate_id = int(payload["sub"])
    except (JWTError, KeyError, TypeError, ValueError):
        raise _UNAUTHORIZED from None
    if is_token_revoked(payload.get("jti"), db=db):
        raise _UNAUTHORIZED
    candidate = candidate_crud.get_by_id(db, candidate_id)
    if candidate is None or not candidate.is_active:
        raise _UNAUTHORIZED
    if token_predates_password_change(candidate, payload):
        raise _UNAUTHORIZED
    return candidate


def get_current_candidate(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> CandidateAccount:
    """Require a valid Candidate Portal session (401 otherwise)."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return candidate_from_token(db, credentials.credentials)


def get_optional_candidate(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> CandidateAccount | None:
    """The signed-in candidate, or ``None`` for a guest.

    Used by the public application submit: guests may still apply, but a
    token that *is* sent must be a valid candidate token (401 otherwise, so
    the portal refreshes it instead of silently applying as a guest).
    """
    if credentials is None:
        return None
    return candidate_from_token(db, credentials.credentials)
