"""Security utilities.

Responsible for:
- password hashing / verification (using bcrypt)
- JWT creation and validation (using python-jose)

Every token carries a ``typ`` claim describing what it may be used for:

=================================  =========================================
Purpose claim                      Accepted by
=================================  =========================================
``access`` (``TOKEN_PURPOSE_ACCESS``)  the ``get_current_user`` guard
``refresh``                        ``POST /api/auth/refresh`` only
``password_reset``                 the reset / skip-reset endpoints only
``role_selection``                 ``POST /api/auth/select-role`` only
``candidate_access``               the Candidate Portal guard only
``candidate_refresh``              ``POST /api/candidate/auth/refresh`` only
``candidate_password_reset``       ``POST /api/candidate/auth/reset-password`` only
=================================  =========================================

Candidate tokens identify a ``candidate_accounts`` row, not a ``users`` row.
Their distinct purposes are the HR/candidate boundary: the HR guard accepts
only ``access`` and the candidate guard only ``candidate_access``, so neither
token type can ever be used on the other side.

Access and refresh tokens also carry a ``role`` claim: the session's active
workspace (see :mod:`app.core.roles`). It is written only here, when the
server signs the token, so a client can never choose or change it.

This separation matters: a reset token travels inside an emailed URL, so it
must never work as a session credential, and a long-lived refresh token must
never be usable to call the API directly.

Backwards compatibility: tokens issued before the ``typ`` claim existed carry
no purpose at all and are treated as access tokens, so existing sessions keep
working across the upgrade.
"""

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

# bcrypt only uses the first 72 bytes of a password; truncate beyond that.
_BCRYPT_MAX_BYTES = 72

#: A real bcrypt digest verified against when there is no stored hash to check
#: (unknown account, or a Google-only account without a local password). Running
#: one bcrypt comparison keeps the login response time roughly constant, so an
#: attacker cannot tell a registered email from an unknown one by timing.
_DUMMY_PASSWORD_HASH = (
    "$2b$12$LAt7bq3wcrFcqgCxQ6NLcOtyoRfLchR20XmJveKNNLSzm4tZ76eZG"
)

#: Bearer credential used to authorize API requests (the default purpose).
TOKEN_PURPOSE_ACCESS = "access"
#: Long-lived credential exchanged for a new access token.
TOKEN_PURPOSE_REFRESH = "refresh"
#: Single-purpose credential embedded in the emailed password-reset link.
TOKEN_PURPOSE_RESET = "password_reset"
#: Short-lived proof that the user just authenticated and must now choose a
#: workspace. Grants nothing else: no API access, no refresh.
TOKEN_PURPOSE_ROLE_SELECTION = "role_selection"
#: Lifetime of a role-selection token: long enough to click a button.
ROLE_SELECTION_TOKEN_EXPIRE_MINUTES = 5

#: Candidate Portal credentials (see the table in the module docstring).
TOKEN_PURPOSE_CANDIDATE_ACCESS = "candidate_access"
TOKEN_PURPOSE_CANDIDATE_REFRESH = "candidate_refresh"
TOKEN_PURPOSE_CANDIDATE_RESET = "candidate_password_reset"
#: Single-purpose credential embedded in the Candidate Portal "verify your
#: email" link. Never accepted as a session credential: the bearer guards accept
#: only the access purposes.
TOKEN_PURPOSE_CANDIDATE_EMAIL_VERIFICATION = "candidate_email_verification"

# NOTE: HR email verification uses a short-lived 6-digit code stored hashed in
# ``email_verifications`` (see app.services.email_verification), not a JWT.


def _password_bytes(password: str) -> bytes:
    """Encode a plain-text password to bytes, honouring the bcrypt length limit."""
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    """Hash a plain-text password and return the salted bcrypt digest."""
    return bcrypt.hashpw(_password_bytes(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str | None) -> bool:
    """Return ``True`` when a plain password matches its stored hash.

    A missing hash (``None``) is never a match, but one bcrypt comparison is
    still performed against a throwaway digest so callers (the login services)
    cannot be timed to learn whether an email is registered or whether an
    account is Google-only. It also means a ``None`` hash can never raise into
    an endpoint.
    """
    if not hashed_password:
        bcrypt.checkpw(_password_bytes(plain_password), _DUMMY_PASSWORD_HASH.encode("utf-8"))
        return False
    try:
        return bcrypt.checkpw(
            _password_bytes(plain_password), hashed_password.encode("utf-8")
        )
    except (ValueError, TypeError):
        return False


def _create_token(
    subject: str | int,
    expires_delta: timedelta,
    purpose: str,
    issued_at: datetime | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Build the common payload for every signed token in the application.

    ``iat`` is what lets a password change revoke the sessions that existed
    before it (see :mod:`app.core.token_registry`); ``typ`` scopes the token to
    a single endpoint group; ``jti`` makes a token individually revokable.

    Args:
        issued_at: Override the ``iat`` instant. Used when a freshly issued pair
            must survive a revocation cutoff recorded in the same second.
    """
    now = issued_at or datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "exp": now + expires_delta,
        "iat": now,
        "typ": purpose,
        "jti": uuid4().hex,
        **(extra_claims or {}),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def _role_claims(role: str | None) -> dict[str, Any] | None:
    return {"role": role} if role else None


def _session_claims(role: str | None, email_verified: bool | None) -> dict[str, Any] | None:
    """Extra claims carried by session tokens (workspace + email verification).

    ``email_verified`` is a UI hint only: the guards always re-read the flag
    from the database, so a stale token can never widen access.
    """
    claims: dict[str, Any] = {}
    if role:
        claims["role"] = role
    if email_verified is not None:
        claims["email_verified"] = email_verified
    return claims or None


def create_access_token(
    subject: str | int,
    expires_delta: timedelta | None = None,
    issued_at: datetime | None = None,
    role: str | None = None,
    email_verified: bool | None = None,
) -> str:
    """Create a signed JWT whose ``sub`` claim identifies the user.

    Args:
        subject: The user identifier to embed in the token.
        expires_delta: Optional custom lifetime; defaults to the configured value.
        issued_at: Optional ``iat`` override (see :func:`_create_token`).
        role: The session's active workspace (``SessionRole`` value).
        email_verified: The account's email-verification state, carried so the
            frontend can show the verification UI before calling a panel
            endpoint. Authoritative checks always read the database.
    """
    return _create_token(
        subject,
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        TOKEN_PURPOSE_ACCESS,
        issued_at=issued_at,
        extra_claims=_session_claims(role, email_verified),
    )


def create_role_selection_token(subject: str | int) -> str:
    """Create the short-lived token that only lets a user pick a workspace."""
    return _create_token(
        subject,
        timedelta(minutes=ROLE_SELECTION_TOKEN_EXPIRE_MINUTES),
        TOKEN_PURPOSE_ROLE_SELECTION,
    )


def create_refresh_token(
    subject: str | int,
    expires_delta: timedelta | None = None,
    issued_at: datetime | None = None,
    role: str | None = None,
    email_verified: bool | None = None,
) -> str:
    """Create a long-lived refresh token for the given user.

    Refresh tokens are only valid at ``POST /api/auth/refresh``; the API guard
    rejects them as bearer credentials.
    """
    return _create_token(
        subject,
        expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        TOKEN_PURPOSE_REFRESH,
        issued_at=issued_at,
        # Carried so a refresh keeps the session's workspace (never upgrades it).
        extra_claims=_session_claims(role, email_verified),
    )


def create_candidate_token(
    candidate_id: int,
    purpose: str,
    issued_at: datetime | None = None,
    email_verified: bool | None = None,
) -> str:
    """Create a Candidate Portal token (access, refresh or password reset).

    Lifetimes match the HR equivalents so both sides behave the same.
    ``email_verified`` is only carried on the session purposes (a UI hint; the
    guard re-reads the database flag).
    """
    lifetimes = {
        TOKEN_PURPOSE_CANDIDATE_ACCESS: timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        TOKEN_PURPOSE_CANDIDATE_REFRESH: timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        TOKEN_PURPOSE_CANDIDATE_RESET: timedelta(
            minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES
        ),
    }
    return _create_token(
        candidate_id,
        lifetimes[purpose],
        purpose,
        issued_at=issued_at,
        extra_claims=(
            _session_claims(None, email_verified)
            if purpose
            in (TOKEN_PURPOSE_CANDIDATE_ACCESS, TOKEN_PURPOSE_CANDIDATE_REFRESH)
            else None
        ),
    )


def create_password_reset_token(
    subject: str | int, expires_delta: timedelta | None = None
) -> str:
    """Create the short-lived, single-purpose token embedded in a reset link.

    Deliberately *not* usable as an access token: :func:`app.dependencies.auth.get_current_user`
    rejects this purpose, so a leaked reset URL cannot call the API.
    """
    return _create_token(
        subject,
        expires_delta
        or timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES),
        TOKEN_PURPOSE_RESET,
    )


def create_candidate_email_verification_token(subject: str | int) -> str:
    """Create the short-lived token embedded in the Candidate verification link.

    Tagged ``typ: "candidate_email_verification"`` so the API bearer guards
    reject it: a forwarded verification link can never be replayed as a session.
    """
    return _create_token(
        subject,
        timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES),
        TOKEN_PURPOSE_CANDIDATE_EMAIL_VERIFICATION,
    )


def decode_candidate_email_verification_token(token: str) -> dict[str, Any]:
    """Decode a Candidate verification token, requiring its purpose.

    Raises:
        JWTError: If the token is invalid, expired or of the wrong purpose.
    """
    return decode_token_for_purpose(token, TOKEN_PURPOSE_CANDIDATE_EMAIL_VERIFICATION)


def token_email_verified(payload: dict[str, Any]) -> bool:
    """Return the token's email-verification hint (True when the claim is absent).

    Tokens minted before this claim existed are treated as verified so existing
    sessions keep working; the guards still read the authoritative DB flag.
    """
    return bool(payload.get("email_verified", True))


def decode_access_token(token: str) -> dict[str, Any]:
    """Validate a JWT signature/expiry and return its payload.

    Raises:
        JWTError: If the token is malformed, expired or has an invalid signature.
    """
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


def token_purpose(payload: dict[str, Any]) -> str:
    """Return the purpose of a decoded token.

    Tokens minted before the ``typ`` claim was introduced have none and are
    treated as access tokens, which keeps already-issued sessions working.
    """
    return str(payload.get("typ") or TOKEN_PURPOSE_ACCESS)


def token_issued_at(payload: dict[str, Any]) -> datetime | None:
    """Return the ``iat`` instant of a decoded token, or ``None`` when absent.

    ``iat`` is serialized by JOSE as integer seconds, so the value is
    second-granular — revocation cutoffs must be compared on the same scale.
    """
    return _timestamp_claim(payload, "iat")


def token_expires_at(payload: dict[str, Any]) -> datetime | None:
    """Return the ``exp`` instant of a decoded token, or ``None`` when absent."""
    return _timestamp_claim(payload, "exp")


def _timestamp_claim(payload: dict[str, Any], claim: str) -> datetime | None:
    """Read a JOSE integer-timestamp claim as an aware UTC datetime."""
    value = payload.get(claim)
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def token_id(payload: dict[str, Any]) -> str | None:
    """Return the unique ``jti`` id of a decoded token, or ``None`` when absent.

    The id is what makes a refresh token single-use: it is deny-listed the
    moment it is exchanged (see :mod:`app.core.token_registry`).
    """
    value = payload.get("jti")
    return str(value) if value is not None else None


def decode_token_for_purpose(token: str, expected_purpose: str) -> dict[str, Any]:
    """Decode a JWT and require it to carry exactly ``expected_purpose``.

    Raises:
        JWTError: If the token is invalid, expired, or issued for a different
            purpose. The message is intentionally generic — callers map it to a
            single user-facing error and must not learn why it failed.
    """
    payload = decode_access_token(token)
    if token_purpose(payload) != expected_purpose:
        raise JWTError("Unexpected token purpose")
    return payload


def decode_reset_token(token: str) -> dict[str, Any]:
    """Decode the credential that authorizes a password-reset / skip-reset call.

    Accepts two purposes:

    * ``password_reset`` — the token carried by the emailed link (the normal
      case, and the only one the frontend ever sees).
    * ``access`` — a live session credential. Proving you hold a valid access
      token is strictly stronger than proving you hold the emailed link, so
      honouring it grants nothing new; it also keeps reset links that were
      mailed before this upgrade working, and lets the user change their
      password from inside the app.

    Refresh tokens are always rejected: they never leave the refresh endpoint.

    Raises:
        JWTError: If the token is invalid, expired or not usable as a reset
            credential.
    """
    return decode_token_for_purposes(
        token, (TOKEN_PURPOSE_RESET, TOKEN_PURPOSE_ACCESS)
    )


def decode_token_for_purposes(
    token: str, allowed_purposes: tuple[str, ...]
) -> dict[str, Any]:
    """Decode a JWT and require its purpose to be one of ``allowed_purposes``.

    Raises:
        JWTError: If the token is invalid, expired or of the wrong purpose.
    """
    payload = decode_access_token(token)
    if token_purpose(payload) not in allowed_purposes:
        raise JWTError("Unexpected token purpose")
    return payload