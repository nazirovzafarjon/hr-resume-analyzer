"""Authentication dependencies.

Provides the dependencies that resolve the authenticated user and the
session's active workspace. JWT validation logic lives in ``core.security``.

Authorization for admin endpoints combines two independent facts:

* the account's **capability** (``User.is_superuser``, read from the database
  on every request, so a demotion takes effect immediately), and
* the session's **active role** (the server-signed ``role`` claim), so a
  superuser who chose the HR workspace cannot use admin endpoints.
"""

from dataclasses import dataclass
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import (
    TOKEN_PURPOSE_ACCESS,
    decode_token_for_purposes,
    token_issued_at,
    token_purpose,
)
from app.core.roles import SessionRole, token_role
from app.core.token_registry import is_session_revoked, is_token_revoked
from app.crud.user import get_user_by_id
from app.models.user import User

_bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentSession:
    """The authenticated user plus what their access token says."""

    user: User
    role: SessionRole
    payload: dict[str, Any]


def get_current_session(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> CurrentSession:
    """Resolve the authenticated user and session from the ``Authorization`` header.

    Only access-purpose bearer credentials are accepted: a password-reset token
    from an emailed link and a refresh token are rejected here even though they
    are correctly signed, so possession of either never grants API access.
    Sessions revoked by a password change are rejected too.

    Raises:
        HTTPException 401: If the token is missing, invalid or stale.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        # A token with no `typ` claim predates purpose tagging and counts as an
        # access token, so sessions issued before the upgrade keep working.
        payload = decode_token_for_purposes(
            credentials.credentials, (TOKEN_PURPOSE_ACCESS,)
        )
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Revocation checks reuse the request's session (one indexed lookup each).
    if token_purpose(payload) != TOKEN_PURPOSE_ACCESS or is_token_revoked(
        payload.get("jti"), db=db
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if is_session_revoked(user_id, token_issued_at(payload), db=db):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = get_user_by_id(db, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return CurrentSession(user=user, role=token_role(payload), payload=payload)


def get_current_user(session: CurrentSession = Depends(get_current_session)) -> User:
    """Resolve the authenticated user (any workspace)."""
    return session.user


def get_current_superuser(session: CurrentSession = Depends(get_current_session)) -> User:
    """Require an admin account **in an admin session**, else raise 403."""
    if not session.user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    if session.role != SessionRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Switch to the admin workspace to use this.",
        )
    return session.user