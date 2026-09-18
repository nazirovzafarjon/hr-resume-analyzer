"""Authentication dependencies.

Provides the dependency that resolves the currently authenticated HR user.
JWT validation logic lives in ``core.security``.
"""

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
from app.core.token_registry import is_session_revoked, is_token_revoked
from app.crud.user import get_user_by_id
from app.models.user import User

_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> User:
    """Resolve the authenticated HR user from the ``Authorization`` header.

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

    if token_purpose(payload) != TOKEN_PURPOSE_ACCESS or is_token_revoked(
        payload.get("jti")
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if is_session_revoked(user_id, token_issued_at(payload)):
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

    return user


def get_current_superuser(current_user: User = Depends(get_current_user)) -> User:
    """Ensure the authenticated user is a superuser, else raise 403."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user