"""Emailed 6-digit code verification for HR accounts.

Security model
--------------
* Codes are six random digits from :func:`secrets.randbelow` (CSPRNG).
* Only a bcrypt hash of the code is stored (``email_verifications.code_hash``).
* A code expires after ``EMAIL_VERIFICATION_CODE_EXPIRE_MINUTES``.
* A code is single-use: verifying (or invalidating on resend) sets ``used_at``.
* Wrong attempts increment ``attempts``; reaching
  ``EMAIL_VERIFICATION_MAX_ATTEMPTS`` invalidates the code so it cannot be
  brute-forced.
* Resend is rate-limited from the stored rows themselves (per-address cooldown
  plus an hourly cap), so no external store is needed and the limit survives
  restarts.
* The raw code is never stored, returned or logged.

Database access lives in ``app.crud.email_verification``; delivery reuses the
existing Resend integration in ``app.services.email``.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.crud import email_verification as verification_crud
from app.models.user import User
from app.services.email import EmailDeliveryResult, send_verification_code_email

logger = logging.getLogger(__name__)

#: Generic failure for every bad-code case (wrong, expired, used, missing), so
#: an attacker cannot tell *why* a code was rejected.
INVALID_CODE_MESSAGE = "Invalid or expired verification code"
ALREADY_VERIFIED_MESSAGE = "Email is already verified"
RESEND_THROTTLED_MESSAGE = (
    "Too many verification code requests. Please try again later."
)
CODE_SENT_MESSAGE = "If that email needs verification, a verification code has been sent."
DEFAULT_DELIVERY_ERROR_MESSAGE = "Unable to deliver verification email. Please try again later."


class InvalidVerificationCode(Exception):
    """The submitted code is wrong, expired, already used or unknown (-> 400)."""

    message = INVALID_CODE_MESSAGE


class EmailAlreadyVerified(Exception):
    """The account's email has already been confirmed (-> 400)."""

    message = ALREADY_VERIFIED_MESSAGE


class ResendThrottledError(Exception):
    """A code was requested again too soon / too often (-> 429)."""

    message = RESEND_THROTTLED_MESSAGE


class EmailDeliveryError(Exception):
    """The email provider failed to accept the verification code (-> 502)."""

    def __init__(self, message: str = DEFAULT_DELIVERY_ERROR_MESSAGE) -> None:
        super().__init__(message)
        self.message = message


def _now() -> datetime:
    return datetime.now(timezone.utc)


def generate_code() -> str:
    """Return a cryptographically secure, zero-padded 6-digit code."""
    return f"{secrets.randbelow(1_000_000):06d}"


def _as_utc(value: datetime) -> datetime:
    """Normalize a DB timestamp to an aware UTC datetime."""
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def issue_code(db: Session, user: User) -> EmailDeliveryResult:
    """Create a fresh code for ``user``, invalidating any previous one, and email it."""
    now = _now()
    verification_crud.invalidate_active(db, user.id, now)

    code = generate_code()
    expires_at = now + timedelta(minutes=settings.EMAIL_VERIFICATION_CODE_EXPIRE_MINUTES)
    verification_crud.create(
        db,
        user_id=user.id,
        code_hash=hash_password(code),
        expires_at=expires_at,
    )
    # The raw code is handed to the mailer only; it is never logged here.
    delivery = send_verification_code_email(user.email, code)
    if isinstance(delivery, bool):
        delivery = EmailDeliveryResult(
            success=delivery,
            error=None if delivery else "Failed to deliver verification email.",
        )

    if not delivery.success:
        logger.warning(
            "Verification code email for user id=%s was not delivered: %s",
            user.id,
            delivery.error,
        )
    return delivery


def verify_code(db: Session, user: User, code: str) -> None:
    """Validate ``code`` for ``user`` and consume the matching record.

    Raises:
        InvalidVerificationCode: For a wrong, expired, used or missing code. The
            attempt counter is incremented on a wrong code, and the code is
            invalidated once the configured maximum is reached.
    """
    now = _now()
    record = verification_crud.get_latest_active(db, user.id)
    if record is None:
        raise InvalidVerificationCode()

    if _as_utc(record.expires_at) <= now:
        verification_crud.save(db, record, {"used_at": now})
        raise InvalidVerificationCode()

    if record.attempts >= settings.EMAIL_VERIFICATION_MAX_ATTEMPTS:
        verification_crud.save(db, record, {"used_at": now})
        raise InvalidVerificationCode()

    if not verify_password(code, record.code_hash):
        attempts = record.attempts + 1
        changes: dict = {"attempts": attempts}
        if attempts >= settings.EMAIL_VERIFICATION_MAX_ATTEMPTS:
            # Exhausted: burn the code so guessing must start over.
            changes["used_at"] = now
        verification_crud.save(db, record, changes)
        raise InvalidVerificationCode()

    # Correct code: single use.
    verification_crud.save(db, record, {"used_at": now})
