"""Authentication business logic.

Responsible for register, login, logout, forgot/reset password and
issuing JWT tokens. Low-level crypto lives in ``core.security`` and
database access in ``crud.user``.
"""

import logging
from datetime import datetime

from jose import JWTError
from sqlalchemy.orm import Session

from app.core.security import (
    TOKEN_PURPOSE_REFRESH,
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    decode_reset_token,
    decode_token_for_purpose,
    hash_password,
    token_expires_at,
    token_id,
    token_issued_at,
    verify_password,
)
from app.core.token_registry import (
    is_session_revoked,
    is_token_revoked,
    revoke_sessions_before,
    revoke_token,
)
from app.crud.user import (
    create_user,
    get_or_create_google_user,
    get_user_by_email,
    get_user_by_id,
)
from app.models.user import User
from app.schemas.auth import RegisterRequest, ResetTokenInfo, Token
from app.schemas.user import UserCreate
from app.services.email import build_reset_link, send_reset_password_email
from app.services.google_auth import GoogleAuthError, authenticate_with_google

logger = logging.getLogger(__name__)


def register_user(db: Session, payload: RegisterRequest) -> User:
    """Register a new HR user and return the created account.

    Raises:
        ValueError: If a user with the same email already exists.
    """
    user_data = UserCreate(
        email=payload.email,
        full_name=payload.full_name,
        password=payload.password,
    )
    return create_user(db, user_data)


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    """Validate credentials and return the matching user, or ``None``.

    Inactive (deactivated) accounts cannot log in. Google-only accounts have
    no password hash and therefore cannot use the password path.
    """
    user = get_user_by_email(db, email)
    if (
        user is None
        or not user.is_active
        or user.hashed_password is None
        or not verify_password(password, user.hashed_password)
    ):
        return None
    return user


async def login_with_google(
    db: Session, code: str, redirect_uri: str | None = None
) -> Token:
    """Sign a user in with a Google authorization ``code``.

    Exchanges the code with Google, resolves/creates the matching local user
    (linking an existing password account when the email already exists) and
    issues the application's own JWT access token. A brand-new Google user is
    created here — this function never rejects an unknown user.

    Args:
        db: Active database session.
        code: The one-time authorization code from the frontend.
        redirect_uri: The URI the code was issued against (``postmessage``
            for the JS popup flow, the configured callback URL for the
            redirect flow). Allowlist-checked by the Google service.

    Raises:
        GoogleAuthError: If Google rejects the code or is unreachable.
        ValueError: If the user cannot be linked (e.g. disabled account).
    """
    logger.info(
        "Google login: exchanging authorization code (…%s) redirect_uri=%r",
        code[-6:] if code else "<empty>",
        redirect_uri,
    )
    profile = await authenticate_with_google(code, redirect_uri)
    logger.info(
        "Google login: profile resolved email=%s google_id=…%s",
        profile.email,
        profile.google_id[-6:],
    )
    user = get_or_create_google_user(
        db,
        google_id=profile.google_id,
        email=profile.email,
        full_name=profile.full_name,
        picture=profile.picture,
    )
    logger.info(
        "Google login: user resolved id=%s email=%s active=%s",
        user.id,
        user.email,
        user.is_active,
    )
    if not user.is_active:
        raise ValueError("This account has been deactivated.")
    return issue_token(user)


def issue_token(user: User, issued_at: datetime | None = None) -> Token:
    """Issue a signed access/refresh pair for the given user.

    The access token authorizes API calls; the refresh token is only ever
    exchanged at ``POST /api/auth/refresh``. ``token_type`` stays ``"bearer"``
    and ``access_token`` keeps its meaning, so every existing client continues
    to work and simply gains an extra field.

    Args:
        issued_at: ``iat`` to embed, used right after a revocation cutoff is
            recorded so the replacement pair is not itself treated as stale.
    """
    return Token(
        access_token=create_access_token(subject=user.id, issued_at=issued_at),
        refresh_token=create_refresh_token(subject=user.id, issued_at=issued_at),
    )


def send_reset_email(db: Session, email: str) -> None:
    """Generate a reset token and deliver the link by email via Resend.

    The token is a short-lived, ``password_reset``-scoped JWT — it is valid only
    at the reset/skip-reset endpoints and is rejected by the API bearer guard, so
    a leaked link cannot be replayed as a session.

    Delivery goes through :mod:`app.services.email` (Resend). When it is
    unavailable — no ``RESEND_API_KEY`` configured, or the API rejects/errors —
    the link is written to the server log instead, which keeps local development
    usable while the endpoint still answers identically for every address.

    The function returns ``None`` regardless of whether the user exists, to avoid
    revealing which emails are registered.
    """
    user = get_user_by_email(db, email)
    if user is None:
        return
    token = create_password_reset_token(subject=user.id)
    # Google-only accounts are handled the same way: the reset page tells them
    # the change will *add* a local password next to Google sign-in, and the
    # "Skip" option just re-issues their session.
    if send_reset_password_email(user.email, token):
        logger.info("Password reset email queued for %s (id=%s)", user.email, user.id)
        return
    logger.warning(
        "Password reset requested for %s (google_only=%s); email delivery "
        "unavailable, reset link: %s",
        user.email,
        user.hashed_password is None,
        build_reset_link(token),
    )


def resolve_reset_token(db: Session, token: str) -> User:
    """Return the active user a reset/skip-reset token belongs to.

    Raises:
        ValueError: If the token is invalid/expired, the account was deleted,
            or the account is deactivated.
    """
    try:
        payload = decode_reset_token(token)
        user_id = int(payload["sub"])
    except (JWTError, KeyError, TypeError, ValueError) as exc:
        raise ValueError("Invalid or expired reset token") from exc

    user = get_user_by_id(db, user_id)
    if user is None:
        raise ValueError("Invalid or expired reset token")
    if not user.is_active:
        raise ValueError("This account has been deactivated.")
    return user


def change_password(db: Session, user: User, current_password: str, new_password: str) -> Token:
    """Change an already authenticated user's password.

    Verifies ``current_password`` against the stored hash, then stores the new
    (bcrypt) hash. On success every session issued *before* the change is
    invalidated — the same behavior as :func:`reset_password` — and a fresh
    access/refresh pair is returned so the caller stays signed in. The pair is
    stamped at the revocation cutoff so it is not caught by its own
    invalidation.

    Raises:
        ValueError: If the account has no local password (Google-only), or the
            current password is incorrect.
    """
    if user.hashed_password is None:
        raise ValueError("This account does not have a password to change.")
    if not verify_password(current_password, user.hashed_password):
        raise ValueError("Current password is incorrect")

    user.hashed_password = hash_password(new_password)
    db.commit()
    db.refresh(user)

    cutoff = revoke_sessions_before(user.id)
    logger.info("Password changed for %s (id=%s)", user.email, user.id)
    return issue_token(user, issued_at=cutoff)


def reset_password(db: Session, token: str, new_password: str) -> Token:
    """Set a new password for the account holding ``token``.

    On success every session issued *before* the change is invalidated, and a
    fresh access/refresh pair is returned so the caller lands signed-in. A
    Google-only account gains its first local password here (both sign-in paths
    then work); it is never locked out of Google sign-in.

    Raises:
        ValueError: If the token is invalid/expired or the user no longer exists.
    """
    user = resolve_reset_token(db, token)

    user.hashed_password = hash_password(new_password)
    db.commit()
    db.refresh(user)

    # Kill every session that predates the change, then mint a pair stamped at
    # the cutoff itself so the new tokens are not caught by their own revocation.
    cutoff = revoke_sessions_before(user.id)
    logger.info("Password reset completed for %s (id=%s)", user.email, user.id)
    return issue_token(user, issued_at=cutoff)


def skip_reset(db: Session, token: str) -> Token:
    """Validate a reset token without touching the password ("Skip" option).

    Issues a fresh access/refresh pair for the existing account. Old sessions
    are deliberately *not* revoked: nothing about the credentials changed, so
    other devices stay signed in.

    Raises:
        ValueError: If the token is invalid/expired or the user no longer exists.
    """
    user = resolve_reset_token(db, token)
    logger.info("Password reset skipped for %s (id=%s)", user.email, user.id)
    return issue_token(user)


def refresh_access_token(db: Session, refresh_token: str) -> Token:
    """Exchange a valid refresh token for a new access/refresh pair.

    The presented token is deny-listed as it is consumed (rotation), so a stolen
    refresh token stops working once the legitimate client has refreshed through
    it — without disturbing the sessions of the user's other devices.

    Raises:
        ValueError: If the token is invalid/expired, is not a refresh token, or
            the account is gone or deactivated.
    """
    try:
        payload = decode_token_for_purpose(refresh_token, TOKEN_PURPOSE_REFRESH)
        user_id = int(payload["sub"])
    except (JWTError, KeyError, TypeError, ValueError) as exc:
        raise ValueError("Invalid or expired refresh token") from exc

    if is_token_revoked(token_id(payload)) or is_session_revoked(
        user_id, token_issued_at(payload)
    ):
        raise ValueError("Invalid or expired refresh token")

    user = get_user_by_id(db, user_id)
    if user is None or not user.is_active:
        raise ValueError("Invalid or expired refresh token")

    # Consume the presented token so it cannot be replayed.
    revoke_token(token_id(payload), expires_at=token_expires_at(payload))
    logger.info("Session refreshed for %s (id=%s)", user.email, user.id)
    return issue_token(user)


def describe_reset_token(db: Session, token: str) -> ResetTokenInfo:
    """Return the account facts a reset page needs to render itself.

    Raises:
        ValueError: If the token is invalid/expired or the account is gone.
    """
    user = resolve_reset_token(db, token)
    return ResetTokenInfo(
        email=user.email,
        full_name=user.full_name,
        has_password=user.hashed_password is not None,
        is_google_account=user.google_id is not None,
    )
