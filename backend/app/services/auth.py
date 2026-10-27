"""Authentication business logic.

Responsible for register, login, logout, forgot/reset password and
issuing JWT tokens. Low-level crypto lives in ``core.security`` and
database access in ``crud.user``.
"""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rate_limit import SlidingWindowLimiter
from app.core.roles import SessionRole, available_roles, token_role
from app.crud import pending_registration as pending_crud
from app.models.pending_registration import PendingRegistration
from app.core.security import (
    ROLE_SELECTION_TOKEN_EXPIRE_MINUTES,
    TOKEN_PURPOSE_REFRESH,
    TOKEN_PURPOSE_ROLE_SELECTION,
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    create_role_selection_token,
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
    get_user_by_google_id,
    get_user_by_id,
)
from app.models.user import User
from app.schemas.auth import (
    RegisterRequest,
    ResetTokenInfo,
    RoleSelectionRequired,
    SignInResult,
    Token,
)
from app.schemas.user import UserCreate
from app.services import audit
from app.services import email_verification as email_verification_service
from app.services import platform_settings as platform_settings_service
from app.services.audit import AuditAction, AuditContext, AuditResource
from app.services.email import (
    EmailDeliveryResult,
    build_reset_link,
    log_development_link,
    send_hr_registration_email,
    send_reset_password_email,
)
from app.services.email_verification import (
    EmailAlreadyVerified,
    InvalidVerificationCode,
    ResendThrottledError,
)
from app.services.google_auth import GoogleAuthError, authenticate_with_google

logger = logging.getLogger(__name__)

REGISTRATION_DISABLED_MESSAGE = "Registration is currently disabled."


INVALID_SELECTION_MESSAGE = "Your sign-in has expired. Please sign in again."
ROLE_NOT_AVAILABLE_MESSAGE = "This workspace is not available for your account."

#: Shown while a registration/panel can still not be used because the email is
#: not confirmed yet.
EMAIL_VERIFICATION_REQUIRED_MESSAGE = "Please verify your email to continue."

# Resend throttling is applied to *every* address (known or not) so the response
# cannot be used to enumerate accounts. Kept in-process, like the Contact form
# limiter; back it with a shared store when the API is scaled out.
_resend_cooldown = SlidingWindowLimiter(
    max_events=1,
    window_seconds=settings.EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS,
)
_resend_hourly = SlidingWindowLimiter(
    max_events=settings.EMAIL_VERIFICATION_MAX_PER_HOUR,
    window_seconds=60 * 60,
)


def reset_verification_throttle() -> None:
    """Clear the resend limiters (used by the test suite for isolation)."""
    _resend_cooldown.reset()
    _resend_hourly.reset()


class RoleNotAvailableError(Exception):
    """The requested workspace is not one this account may use (-> 403)."""

    def __init__(self) -> None:
        super().__init__(ROLE_NOT_AVAILABLE_MESSAGE)


class RegistrationDisabledError(ValueError):
    """New accounts are switched off in the admin Settings page."""

    def __init__(self) -> None:
        super().__init__(REGISTRATION_DISABLED_MESSAGE)


def _mark_signed_in(db: Session, user: User) -> None:
    """Stamp ``last_login_at`` (the admin panel's "last activity")."""
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()


def record_sign_in(
    db: Session, user: User, method: str, context: AuditContext | None = None
) -> None:
    """Remember an interactive sign-in and put it in the audit trail."""
    _mark_signed_in(db, user)
    audit.record(
        db,
        AuditAction.LOGIN,
        resource_type=AuditResource.USER,
        resource_id=user.id,
        actor=user,
        details={"method": method},
        context=context,
    )


def initiate_registration(
    db: Session, payload: RegisterRequest, context: AuditContext | None = None
) -> tuple[PendingRegistration, EmailDeliveryResult]:
    """Initiate a two-phase HR registration.

    Stores the pending registration in ``pending_registrations`` and emails
    a secure verification link and code.
    No row is created in ``users`` and zero session tokens are issued until
    verification succeeds.

    Raises:
        RegistrationDisabledError: Registration disabled in platform settings.
        ValueError: An account with this email already exists in users.

    Delivery failure does not raise: the pending row is persisted first and the
    returned :class:`EmailDeliveryResult` tells the caller whether the email was
    accepted, so a provider rejection is reported honestly instead of discarding
    the recoverable registration state.
    """
    if not platform_settings_service.registration_enabled(db):
        raise RegistrationDisabledError()

    norm_email = payload.email.strip().lower()
    existing_user = get_user_by_email(db, norm_email)
    if existing_user is not None:
        raise ValueError("A user with this email already exists")

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    code = email_verification_service.generate_code()
    code_hash = hash_password(code)
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.EMAIL_VERIFICATION_CODE_EXPIRE_MINUTES
    )
    hashed_password = hash_password(payload.password)

    # Persist the pending registration *before* attempting delivery. This row is
    # the recoverable state: if the provider rejects the message, the user can
    # request a new verification code (POST /api/auth/resend-verification-code)
    # instead of being left with no way to finish registering. No permanent user
    # and no session token exist until verification succeeds.
    pending = pending_crud.create_or_update(
        db,
        email=norm_email,
        full_name=payload.full_name.strip(),
        hashed_password=hashed_password,
        token_hash=token_hash,
        code_hash=code_hash,
        expires_at=expires_at,
    )

    delivery = send_hr_registration_email(norm_email, raw_token, code)
    if not delivery.success:
        # Delivery is best-effort here: the pending row is already durable, so
        # the caller reports `verification_email_sent: false` (never a false
        # success) and the user retries through the resend endpoint.
        logger.warning(
            "Registration email delivery failed for %s: %s (status=%s)",
            norm_email,
            delivery.error,
            delivery.status_code,
        )
    else:
        logger.info("Pending registration created for %s (id=%s)", norm_email, pending.id)
    return pending, delivery


def register_user(
    db: Session, payload: RegisterRequest, context: AuditContext | None = None
) -> User:
    """Register a new HR user directly (internal / test helper).

    Raises:
        RegistrationDisabledError: An admin has switched registration off.
        ValueError: If a user with the same email already exists.
    """
    if not platform_settings_service.registration_enabled(db):
        raise RegistrationDisabledError()
    user_data = UserCreate(
        email=payload.email,
        full_name=payload.full_name,
        password=payload.password,
    )
    user = create_user(db, user_data, is_email_verified=False)
    _mark_signed_in(db, user)
    audit.record(
        db,
        AuditAction.REGISTER,
        resource_type=AuditResource.USER,
        resource_id=user.id,
        actor=user,
        details={"method": "password"},
        context=context,
    )
    delivery = email_verification_service.issue_code(db, user)
    user.verification_email_sent = delivery.success
    user.email_delivery_error = delivery.error if not delivery.success else None
    return user


def _claim_pending_registration(db: Session, pending_id: int, when: datetime) -> bool:
    """Atomically claim a pending registration for verification.

    A conditional ``UPDATE … WHERE consumed_at IS NULL`` is the concurrency
    guard: the database, not a Python read-then-write, decides the winner, so
    two simultaneous confirmations (a double-click, a retried request) can never
    both create a user. The update is *not* committed here; the caller commits
    it together with the user insert so the two are one transaction.
    """
    result = db.execute(
        update(PendingRegistration)
        .where(
            PendingRegistration.id == pending_id,
            PendingRegistration.consumed_at.is_(None),
        )
        .values(consumed_at=when)
    )
    return result.rowcount == 1


def _create_verified_user(db: Session, pending: PendingRegistration) -> User:
    """Insert the permanent, verified user and commit the claimed pending row.

    The unique-email constraint is the last line of defence: if another path
    created the account first, the insert fails and the whole transaction
    (including the pending claim) is rolled back, leaving the row recoverable.
    """
    user = User(
        email=pending.email,
        full_name=pending.full_name,
        hashed_password=pending.hashed_password,
        is_email_verified=True,
        is_active=True,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise EmailAlreadyVerified() from exc
    db.refresh(user)
    return user


def verify_email(
    db: Session,
    token: str | None = None,
    email: str | None = None,
    code: str | None = None,
    audit_ctx: AuditContext | None = None,
) -> User:
    """Confirm an HR registration with either a verification link token or email+code.

    Atomically claims the pending registration, creates the permanent user in
    ``users`` with ``is_email_verified = True``, and returns the created user.

    Raises:
        InvalidVerificationCode: Bad, expired, already-used token/code or too many attempts.
        EmailAlreadyVerified: The email address is already verified in users.
    """
    now = datetime.now(timezone.utc)
    # -------------------------------------------------------------------------
    # Case 1: Verification token from emailed link
    # -------------------------------------------------------------------------
    if token:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        pending = pending_crud.get_by_token_hash(db, token_hash)
        if pending is None:
            raise InvalidVerificationCode("Invalid or expired verification link")
        if pending.is_consumed:
            raise InvalidVerificationCode("This verification link has already been used")
        if pending.is_expired:
            raise InvalidVerificationCode("This verification link has expired")
        if pending.attempts >= settings.EMAIL_VERIFICATION_MAX_ATTEMPTS:
            raise InvalidVerificationCode("Too many failed attempts. This link is no longer valid.")

        existing = get_user_by_email(db, pending.email)
        if existing is not None:
            pending_crud.mark_consumed(db, pending)
            raise EmailAlreadyVerified()

        if not _claim_pending_registration(db, pending.id, now):
            db.rollback()
            raise InvalidVerificationCode("This verification link has already been used")

        user = _create_verified_user(db, pending)
        _mark_signed_in(db, user)
        audit.record(
            db,
            AuditAction.REGISTER,
            resource_type=AuditResource.USER,
            resource_id=user.id,
            actor=user,
            details={"method": "verification_link"},
            context=audit_ctx,
        )
        logger.info("User created and verified via link token: %s (id=%s)", user.email, user.id)
        return user

    # -------------------------------------------------------------------------
    # Case 2: Verification code (+ email)
    # -------------------------------------------------------------------------
    if email and code:
        norm_email = email.strip().lower()
        pending = pending_crud.get_by_email(db, norm_email)
        if pending is not None:
            if pending.is_consumed:
                raise InvalidVerificationCode("Verification code has already been used")
            if pending.is_expired:
                raise InvalidVerificationCode("Verification code has expired")
            if pending.attempts >= settings.EMAIL_VERIFICATION_MAX_ATTEMPTS:
                raise InvalidVerificationCode("Too many failed attempts. Please request a new code.")

            if not pending.code_hash or not verify_password(code, pending.code_hash):
                pending.attempts += 1
                db.commit()
                raise InvalidVerificationCode()

            existing = get_user_by_email(db, pending.email)
            if existing is not None:
                pending_crud.mark_consumed(db, pending)
                raise EmailAlreadyVerified()

            if not _claim_pending_registration(db, pending.id, now):
                db.rollback()
                raise InvalidVerificationCode("Verification code has already been used")

            user = _create_verified_user(db, pending)
            _mark_signed_in(db, user)
            audit.record(
                db,
                AuditAction.REGISTER,
                resource_type=AuditResource.USER,
                resource_id=user.id,
                actor=user,
                details={"method": "verification_code"},
                context=audit_ctx,
            )
            logger.info("User created and verified via code: %s (id=%s)", user.email, user.id)
            return user

        # Fallback for pre-existing unverified users in users table
        user = get_user_by_email(db, norm_email)
        if user is None or not user.is_active:
            verify_password(code, None)
            raise InvalidVerificationCode()
        if user.is_email_verified:
            raise EmailAlreadyVerified()

        email_verification_service.verify_code(db, user, code)
        user.is_email_verified = True
        db.commit()
        db.refresh(user)
        logger.info("Email verified for existing user %s (id=%s)", user.email, user.id)
        return user

    raise InvalidVerificationCode("Verification token or code required")


def prepare_resend_verification(
    db: Session, email: str
) -> tuple[str, str, str] | None:
    """Regenerate verification credentials for an address, without sending.

    Performs the throttling and the database writes synchronously (so the
    caller keeps its 429 behaviour and the state is durable), and returns
    ``(email, raw_token, code)`` for the caller to dispatch. Returns ``None``
    when there is nothing to send (unknown or already-verified address).

    The legacy pre-existing-unverified-user path cannot be split cleanly (the
    code-issuing helper both writes and sends), so it is dispatched here and
    reports nothing; the caller still answers generically.

    Raises:
        ResendThrottledError: too soon / too many requests.
        EmailAlreadyVerified: the address is already confirmed.
    """
    key = email.strip().lower()
    if not _resend_cooldown.check(key) or not _resend_hourly.check(key):
        raise ResendThrottledError()

    user = get_user_by_email(db, key)
    if user is not None and user.is_email_verified:
        raise EmailAlreadyVerified()

    pending = pending_crud.get_by_email(db, key)
    if pending is not None and not pending.is_consumed:
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        code = email_verification_service.generate_code()
        code_hash = hash_password(code)
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=settings.EMAIL_VERIFICATION_CODE_EXPIRE_MINUTES
        )

        # Persist the fresh credentials before dispatch: the response no longer
        # waits for the provider, and the old link is invalidated immediately.
        pending.token_hash = token_hash
        pending.code_hash = code_hash
        pending.expires_at = expires_at
        pending.attempts = 0
        pending.last_sent_at = datetime.now(timezone.utc)
        db.commit()
        return key, raw_token, code

    if user is not None and not user.is_email_verified and user.is_active:
        # Legacy single-phase account: reuse the existing code-issuing helper.
        delivery = email_verification_service.issue_code(db, user)
        if not delivery.success:
            logger.warning(
                "Verification code email delivery failed for user id=%s: %s",
                user.id,
                delivery.error,
            )
        return None

    return None


def dispatch_registration_email(email: str, raw_token: str, code: str) -> None:
    """Send a verification email (link + code); safe to run in the background.

    Never raises: delivery failures are logged, which is what lets the public
    resend endpoint answer generically without revealing whether an address is
    registered.
    """
    delivery = send_hr_registration_email(email, raw_token, code)
    if not delivery.success:
        logger.warning(
            "Verification email delivery failed for %s: %s (status=%s)",
            email,
            delivery.error,
            delivery.status_code,
        )


def cleanup_expired_pending(db: Session, max_age_hours: int = 24) -> int:
    """Purge pending registrations expired or consumed longer than max_age_hours ago."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    return pending_crud.delete_expired(db, cutoff)


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    """Validate credentials and return the matching user, or ``None``.

    Inactive (deactivated) accounts cannot log in. Google-only accounts have
    no password hash and therefore cannot use the password path.
    """
    user = get_user_by_email(db, email)
    if user is None or user.hashed_password is None:
        # Nothing to compare against (unknown email / Google-only account).
        # Still spend one bcrypt verification so the response time cannot be
        # used to enumerate accounts (see core.security.verify_password).
        verify_password(password, None)
        return None
    if not user.is_active or not verify_password(password, user.hashed_password):
        return None
    return user


async def login_with_google(
    db: Session,
    code: str,
    redirect_uri: str | None = None,
    context: AuditContext | None = None,
) -> SignInResult:
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
        RegistrationDisabledError: The Google account is unknown and an admin
            has switched registration off.
        ValueError: If the user cannot be linked (e.g. disabled account).
    """
    logger.info(
        "Google login: exchanging authorization code (…%s) redirect_uri=%r",
        code[-6:] if code else "<empty>",
        redirect_uri,
    )
    profile = await authenticate_with_google(code, redirect_uri)
    if not profile.email_verified:
        # Linking by an unverified address would let an attacker claim an
        # existing local account. Google verifies consumer emails, so this only
        # rejects genuinely unverified identities.
        raise GoogleAuthError(
            "Your Google email address is not verified, so it cannot be used to sign in."
        )
    logger.info(
        "Google login: profile resolved email=%s google_id=…%s",
        profile.email,
        profile.google_id[-6:],
    )
    # A first-time Google sign-in *creates* an account, so it obeys the same
    # registration switch as the sign-up form. Existing accounts (matched by
    # Google id or email, exactly like get_or_create_google_user) always pass.
    is_new = (
        get_user_by_google_id(db, profile.google_id) is None
        and get_user_by_email(db, profile.email) is None
    )
    if is_new and not platform_settings_service.registration_enabled(db):
        raise RegistrationDisabledError()
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
    if is_new:
        audit.record(
            db,
            AuditAction.REGISTER,
            resource_type=AuditResource.USER,
            resource_id=user.id,
            actor=user,
            details={"method": "google"},
            context=context,
        )
    record_sign_in(db, user, "google", context)
    return begin_session(user)


def issue_token(
    user: User,
    role: SessionRole = SessionRole.USER,
    issued_at: datetime | None = None,
) -> Token:
    """Issue a signed access/refresh pair for the given user and workspace.

    The access token authorizes API calls; the refresh token is only ever
    exchanged at ``POST /api/auth/refresh``. ``token_type`` stays ``"bearer"``
    and ``access_token`` keeps its meaning, so every existing client continues
    to work and simply gains extra fields.

    Args:
        role: The session's workspace. Callers must only pass a role taken
            from :func:`available_roles` -- never one supplied by a client.
        issued_at: ``iat`` to embed, used right after a revocation cutoff is
            recorded so the replacement pair is not itself treated as stale.
    """
    if role not in available_roles(user):
        # Defensive: a bug upstream must never mint an admin session.
        role = SessionRole.USER
    return Token(
        access_token=create_access_token(
            subject=user.id,
            issued_at=issued_at,
            role=role.value,
            email_verified=user.is_email_verified,
        ),
        refresh_token=create_refresh_token(
            subject=user.id,
            issued_at=issued_at,
            role=role.value,
            email_verified=user.is_email_verified,
        ),
        active_role=role,
        is_email_verified=user.is_email_verified,
        requires_email_verification=not user.is_email_verified,
        verification_email_sent=getattr(user, "verification_email_sent", True),
        email_delivery_error=getattr(user, "email_delivery_error", None),
    )


def begin_session(user: User, issued_at: datetime | None = None) -> SignInResult:
    """Finish an interactive sign-in.

    One available workspace -> a session for it straight away (every HR-only
    account). Several -> no session yet: a short-lived selection token the
    user exchanges at ``POST /api/auth/select-role`` after choosing. Admin is
    never picked automatically, even for superusers.
    """
    roles = available_roles(user)
    if len(roles) == 1:
        return issue_token(user, roles[0], issued_at=issued_at)
    return RoleSelectionRequired(
        selection_token=create_role_selection_token(user.id),
        available_roles=roles,
        full_name=user.full_name,
        expires_in=ROLE_SELECTION_TOKEN_EXPIRE_MINUTES * 60,
    )


def _audit_role(
    db: Session,
    action: str,
    user: User,
    role: SessionRole,
    context: AuditContext | None,
    previous: SessionRole | None = None,
) -> None:
    details: dict = {"role": role.value}
    if previous is not None:
        details["from_role"] = previous.value
    audit.record(
        db,
        action,
        resource_type=AuditResource.USER,
        resource_id=user.id,
        actor=user,
        details=details,
        context=context,
    )


def select_role(
    db: Session,
    selection_token: str,
    role: SessionRole,
    context: AuditContext | None = None,
) -> Token:
    """Exchange a role-selection token for a session in the chosen workspace.

    Raises:
        ValueError: The selection token is invalid, expired, already used, or
            its account is gone / deactivated (-> 401, sign in again).
        RoleNotAvailableError: The account may not use ``role`` (-> 403).
    """
    try:
        payload = decode_token_for_purpose(selection_token, TOKEN_PURPOSE_ROLE_SELECTION)
        user_id = int(payload["sub"])
    except (JWTError, KeyError, TypeError, ValueError) as exc:
        raise ValueError(INVALID_SELECTION_MESSAGE) from exc

    if is_token_revoked(token_id(payload)) or is_session_revoked(user_id, token_issued_at(payload)):
        raise ValueError(INVALID_SELECTION_MESSAGE)
    user = get_user_by_id(db, user_id)
    if user is None or not user.is_active:
        raise ValueError(INVALID_SELECTION_MESSAGE)
    # The capability is re-read from the database: a request body saying
    # "admin" is only honoured for an account that really is a superuser.
    if role not in available_roles(user):
        logger.warning("Role selection refused: user_id=%s role=%s", user.id, role.value)
        raise RoleNotAvailableError()

    # Single use: the token cannot mint a second session.
    revoke_token(token_id(payload), expires_at=token_expires_at(payload))
    _audit_role(db, AuditAction.ROLE_SELECTED, user, role, context)
    return issue_token(user, role)


def switch_role(
    db: Session,
    user: User,
    current_payload: dict,
    role: SessionRole,
    context: AuditContext | None = None,
) -> Token:
    """Move the current session to another workspace.

    The presented access token is revoked, so the old workspace context stops
    working at once; the client replaces both tokens with the returned pair.

    Raises:
        RoleNotAvailableError: The account may not use ``role`` (-> 403).
    """
    if role not in available_roles(user):
        logger.warning("Role switch refused: user_id=%s role=%s", user.id, role.value)
        raise RoleNotAvailableError()
    previous = token_role(current_payload)
    revoke_token(token_id(current_payload), expires_at=token_expires_at(current_payload))
    _audit_role(db, AuditAction.ROLE_SWITCHED, user, role, context, previous=previous)
    return issue_token(user, role)


def logout(user: User, access_payload: dict, refresh_token: str | None) -> None:
    """Revoke the presented access token and, when given, its refresh token.

    Only a refresh token belonging to the same user is revoked; anything else
    is ignored (logout must always succeed for the caller).
    """
    revoke_token(token_id(access_payload), expires_at=token_expires_at(access_payload))
    if not refresh_token:
        return
    try:
        payload = decode_token_for_purpose(refresh_token, TOKEN_PURPOSE_REFRESH)
    except JWTError:
        return
    if str(payload.get("sub")) == str(user.id):
        revoke_token(token_id(payload), expires_at=token_expires_at(payload))


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
    log_development_link(
        f"Password reset requested for {user.email} "
        f"(google_only={user.hashed_password is None}) but email delivery is unavailable.",
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


def change_password(
    db: Session,
    user: User,
    current_password: str,
    new_password: str,
    context: AuditContext | None = None,
    role: SessionRole = SessionRole.USER,
) -> Token:
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
    audit.record(
        db,
        AuditAction.PASSWORD_CHANGE,
        resource_type=AuditResource.USER,
        resource_id=user.id,
        actor=user,
        context=context,
    )
    # Same workspace as the session that changed the password.
    return issue_token(user, role, issued_at=cutoff)


def reset_password(
    db: Session, token: str, new_password: str, context: AuditContext | None = None
) -> SignInResult:
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
    _mark_signed_in(db, user)
    audit.record(
        db,
        AuditAction.PASSWORD_RESET,
        resource_type=AuditResource.USER,
        resource_id=user.id,
        actor=user,
        context=context,
    )
    return begin_session(user, issued_at=cutoff)


def skip_reset(db: Session, token: str, context: AuditContext | None = None) -> SignInResult:
    """Validate a reset token without touching the password ("Skip" option).

    Issues a fresh access/refresh pair for the existing account. Old sessions
    are deliberately *not* revoked: nothing about the credentials changed, so
    other devices stay signed in.

    Raises:
        ValueError: If the token is invalid/expired or the user no longer exists.
    """
    user = resolve_reset_token(db, token)
    logger.info("Password reset skipped for %s (id=%s)", user.email, user.id)
    record_sign_in(db, user, "reset_link", context)
    return begin_session(user)


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
    # A refresh proves the session is in use, so it counts as activity; it is
    # not audited (it happens silently every hour for every open tab).
    _mark_signed_in(db, user)
    # Keep the session's workspace. issue_token() drops it back to HR if the
    # account lost admin capability since the session started.
    return issue_token(user, token_role(payload))


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
