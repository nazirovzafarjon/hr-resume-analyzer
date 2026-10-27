"""Candidate Portal authentication: register, sign in, refresh, reset password.

Reuses the platform's security primitives (bcrypt hashing, signed JWTs, the
``jti`` deny-list, the reset email) with candidate-only token purposes; see
``app.models.candidate_account`` for why candidates have their own identity.

"Sign out everywhere" after a password change/reset uses the account's
``password_changed_at``: tokens issued before it are rejected. JOSE stores
``iat`` in whole seconds, so the cutoff is truncated to the second and the
fresh pair is stamped with that same instant (it must not be caught by its own
cutoff).
"""

import logging
from datetime import datetime, timezone
from typing import Any

from jose import JWTError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rate_limit import SlidingWindowLimiter
from app.core.security import (
    TOKEN_PURPOSE_CANDIDATE_ACCESS,
    TOKEN_PURPOSE_CANDIDATE_REFRESH,
    TOKEN_PURPOSE_CANDIDATE_RESET,
    create_candidate_email_verification_token,
    create_candidate_token,
    decode_candidate_email_verification_token,
    decode_token_for_purpose,
    hash_password,
    token_expires_at,
    token_id,
    token_issued_at,
    verify_password,
)
from app.core.token_registry import is_token_revoked, revoke_token
from app.crud import candidate_account as candidate_crud
from app.models.candidate_account import CandidateAccount
from app.schemas.candidate import CandidateTokens
from app.services.email import (
    build_reset_link,
    build_verify_email_link,
    log_development_link,
    send_reset_password_email,
    send_verification_email,
)

logger = logging.getLogger(__name__)

RESET_PAGE_PATH = "/candidate/reset-password"
VERIFY_PAGE_PATH = "/candidate/verify-email"

EMAIL_VERIFICATION_SENT_MESSAGE = (
    "If that email needs verification, a verification link has been sent."
)

#: Public resend guard: at most one request per address per cooldown window.
_resend_limiter = SlidingWindowLimiter(
    max_events=1,
    window_seconds=settings.EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS,
)


def reset_verification_throttle() -> None:
    """Clear the resend cooldown (used by the test suite for isolation)."""
    _resend_limiter.reset()


class CandidateAuthError(ValueError):
    """A sign-in / token problem with a message safe to show the visitor."""


class DuplicateEmailError(CandidateAuthError):
    def __init__(self) -> None:
        super().__init__("An account with this email already exists.")


class ResendThrottledError(Exception):
    """A verification email was requested again too soon (-> 429)."""

    message = "Please wait a moment before requesting another verification email."


def _now_seconds() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def token_predates_password_change(candidate: CandidateAccount, payload: dict[str, Any]) -> bool:
    """True when the token was issued before the account's last password change."""
    cutoff = candidate.password_changed_at
    if cutoff is None:
        return False
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)
    issued = token_issued_at(payload)
    return issued is None or issued < cutoff.replace(microsecond=0)


def issue_tokens(candidate: CandidateAccount, issued_at: datetime | None = None) -> CandidateTokens:
    """A fresh candidate access/refresh pair (with the verification hint)."""
    return CandidateTokens(
        access_token=create_candidate_token(
            candidate.id,
            TOKEN_PURPOSE_CANDIDATE_ACCESS,
            issued_at,
            email_verified=candidate.is_email_verified,
        ),
        refresh_token=create_candidate_token(
            candidate.id,
            TOKEN_PURPOSE_CANDIDATE_REFRESH,
            issued_at,
            email_verified=candidate.is_email_verified,
        ),
    )


def _mark_signed_in(db: Session, candidate: CandidateAccount) -> None:
    candidate_crud.update(db, candidate, {"last_login_at": datetime.now(timezone.utc)})


def register(db: Session, *, email: str, full_name: str, password: str, phone: str | None) -> CandidateAccount:
    """Create a candidate account (email must be unused by another candidate)."""
    if candidate_crud.get_by_email(db, email) is not None:
        raise DuplicateEmailError()
    try:
        candidate = candidate_crud.create(
            db, email=email, full_name=full_name, password=password, phone=phone
        )
    except IntegrityError as exc:
        # Two concurrent registrations raced on the unique email.
        db.rollback()
        raise DuplicateEmailError() from exc
    _mark_signed_in(db, candidate)
    send_email_verification(db, candidate)
    logger.info("Candidate account registered (id=%s)", candidate.id)
    return candidate


def send_email_verification(db: Session, candidate: CandidateAccount) -> None:
    """Mint a fresh candidate verification token, record its time and email it."""
    issued_at = datetime.now(timezone.utc).replace(microsecond=0)
    candidate.email_verification_issued_at = issued_at
    candidate_crud.update(db, candidate, {"email_verification_issued_at": issued_at})

    token = create_candidate_email_verification_token(candidate.id)
    if send_verification_email(candidate.email, token, VERIFY_PAGE_PATH):
        logger.info("Candidate verification email queued (id=%s)", candidate.id)
        return
    log_development_link(
        f"Candidate email verification requested (id={candidate.id}) but delivery is unavailable.",
        build_verify_email_link(token, VERIFY_PAGE_PATH),
    )


def verify_email(db: Session, token: str) -> CandidateAccount:
    """Confirm a candidate account from the emailed verification token.

    Raises:
        CandidateAuthError: invalid/expired/superseded/used token, or gone /
            deactivated account.
    """
    invalid = CandidateAuthError("This verification link is invalid or has expired.")
    try:
        payload = decode_candidate_email_verification_token(token)
        candidate_id = int(payload["sub"])
    except (JWTError, KeyError, TypeError, ValueError) as exc:
        raise invalid from exc

    if is_token_revoked(token_id(payload), db=db):
        raise CandidateAuthError("This verification link has already been used.")

    candidate = candidate_crud.get_by_id(db, candidate_id)
    if candidate is None:
        raise invalid
    if not candidate.is_active:
        raise CandidateAuthError("This account has been deactivated.")

    issued_at = token_issued_at(payload)
    if candidate.email_verification_issued_at is not None:
        cutoff = candidate.email_verification_issued_at
        if cutoff.tzinfo is None:
            cutoff = cutoff.replace(tzinfo=timezone.utc)
        if issued_at is None or issued_at < cutoff.replace(microsecond=0):
            raise CandidateAuthError(
                "This verification link has been replaced by a newer one."
            )

    candidate_crud.update(
        db, candidate, {"is_email_verified": True, "email_verification_issued_at": None}
    )
    revoke_token(token_id(payload), expires_at=token_expires_at(payload), db=db)
    logger.info("Candidate email verified (id=%s)", candidate.id)
    return candidate


def resend_verification_email(db: Session, email: str) -> None:
    """Send a fresh candidate verification link when one is needed.

    Silent about account existence/verification state; throttled per address.
    """
    key = email.strip().lower()
    if not _resend_limiter.check(key):
        raise ResendThrottledError()

    candidate = candidate_crud.get_by_email(db, email)
    if candidate is None or candidate.is_email_verified or not candidate.is_active:
        return
    send_email_verification(db, candidate)


from app.services.google_auth import GoogleAuthError, authenticate_with_google


def authenticate(db: Session, email: str, password: str) -> CandidateAccount:
    """Return the account for valid credentials, else raise one generic error.

    A deactivated account gets its own message only after the password was
    verified, so it never reveals which emails are registered.
    Google-only accounts have no hashed_password and cannot use the password path.
    """
    candidate = candidate_crud.get_by_email(db, email)
    if candidate is None or candidate.hashed_password is None:
        # Unknown email / Google-only account: still spend one bcrypt
        # verification so timing cannot reveal whether the account exists.
        verify_password(password, None)
        raise CandidateAuthError("Incorrect email or password.")
    if not verify_password(password, candidate.hashed_password):
        raise CandidateAuthError("Incorrect email or password.")
    if not candidate.is_active:
        raise CandidateAuthError("This account has been deactivated.")
    _mark_signed_in(db, candidate)
    return candidate


async def login_with_google(
    db: Session,
    code: str,
    redirect_uri: str | None = None,
) -> CandidateAccount:
    """Sign a candidate in with a Google authorization ``code``.

    Exchanges the code with Google, resolves/creates the matching candidate account
    (linking an existing candidate account when the email matches).
    """
    profile = await authenticate_with_google(code, redirect_uri)
    if not profile.email_verified:
        raise GoogleAuthError(
            "Your Google email address is not verified, so it cannot be used to sign in."
        )
    candidate = candidate_crud.get_or_create_google_candidate(
        db,
        google_id=profile.google_id,
        email=profile.email,
        full_name=profile.full_name,
        picture=profile.picture,
    )
    if not candidate.is_active:
        raise CandidateAuthError("This account has been deactivated.")
    _mark_signed_in(db, candidate)
    logger.info("Candidate Google login succeeded (id=%s, email=%s)", candidate.id, candidate.email)
    return candidate


def refresh(db: Session, refresh_token: str) -> CandidateTokens:
    """Rotate a candidate refresh token into a new pair (the old one is consumed)."""
    invalid = CandidateAuthError("Invalid or expired refresh token")
    try:
        payload = decode_token_for_purpose(refresh_token, TOKEN_PURPOSE_CANDIDATE_REFRESH)
        candidate_id = int(payload["sub"])
    except (JWTError, KeyError, TypeError, ValueError) as exc:
        raise invalid from exc
    if is_token_revoked(token_id(payload), db=db):
        raise invalid
    candidate = candidate_crud.get_by_id(db, candidate_id)
    if candidate is None or not candidate.is_active or token_predates_password_change(candidate, payload):
        raise invalid
    revoke_token(token_id(payload), expires_at=token_expires_at(payload), db=db)
    _mark_signed_in(db, candidate)
    return issue_tokens(candidate)


def logout(db: Session, access_payload: dict[str, Any], refresh_token: str | None) -> None:
    """Deny-list the current access token and, when given, its refresh token."""
    revoke_token(token_id(access_payload), expires_at=token_expires_at(access_payload), db=db)
    if not refresh_token:
        return
    try:
        payload = decode_token_for_purpose(refresh_token, TOKEN_PURPOSE_CANDIDATE_REFRESH)
    except JWTError:
        return
    if payload.get("sub") == access_payload.get("sub"):
        revoke_token(token_id(payload), expires_at=token_expires_at(payload), db=db)


def _set_password(db: Session, candidate: CandidateAccount, new_password: str) -> datetime:
    """Store a new password and revoke every older session; return the cutoff."""
    cutoff = _now_seconds()
    candidate_crud.update(
        db,
        candidate,
        {"hashed_password": hash_password(new_password), "password_changed_at": cutoff},
    )
    return cutoff


def change_password(
    db: Session, candidate: CandidateAccount, current_password: str, new_password: str
) -> CandidateTokens:
    """Change the password of a signed-in candidate; returns a fresh pair."""
    if candidate.hashed_password is None:
        # Google-only account: it has no password to re-authenticate against.
        # Guard here so bcrypt is never called with a NULL hash (-> 500).
        raise CandidateAuthError("This account does not have a password to change.")
    if not verify_password(current_password, candidate.hashed_password):
        raise CandidateAuthError("Current password is incorrect")
    cutoff = _set_password(db, candidate, new_password)
    logger.info("Candidate password changed (id=%s)", candidate.id)
    return issue_tokens(candidate, issued_at=cutoff)


def send_reset_email(db: Session, email: str) -> None:
    """Email a reset link when the account exists; silent otherwise (no enumeration)."""
    candidate = candidate_crud.get_by_email(db, email)
    if candidate is None or not candidate.is_active:
        return
    token = create_candidate_token(candidate.id, TOKEN_PURPOSE_CANDIDATE_RESET)
    if send_reset_password_email(candidate.email, token, RESET_PAGE_PATH):
        logger.info("Candidate password reset email queued (id=%s)", candidate.id)
        return
    log_development_link(
        f"Candidate password reset requested (id={candidate.id}) but delivery is unavailable.",
        build_reset_link(token, RESET_PAGE_PATH),
    )


def reset_password(db: Session, token: str, new_password: str) -> tuple[CandidateAccount, CandidateTokens]:
    """Set a new password from an emailed reset link and sign the candidate in.

    The link is single-use: its ``jti`` is deny-listed, and the password
    change also invalidates every older token.
    """
    invalid = CandidateAuthError("This reset link is invalid or has expired.")
    try:
        payload = decode_token_for_purpose(token, TOKEN_PURPOSE_CANDIDATE_RESET)
        candidate_id = int(payload["sub"])
    except (JWTError, KeyError, TypeError, ValueError) as exc:
        raise invalid from exc
    if is_token_revoked(token_id(payload), db=db):
        raise invalid
    candidate = candidate_crud.get_by_id(db, candidate_id)
    if candidate is None or not candidate.is_active or token_predates_password_change(candidate, payload):
        raise invalid
    revoke_token(token_id(payload), expires_at=token_expires_at(payload), db=db)
    cutoff = _set_password(db, candidate, new_password)
    _mark_signed_in(db, candidate)
    logger.info("Candidate password reset completed (id=%s)", candidate.id)
    return candidate, issue_tokens(candidate, issued_at=cutoff)
