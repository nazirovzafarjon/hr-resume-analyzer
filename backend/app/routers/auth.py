"""Authentication API endpoints.

Register, login, logout, forgot/reset password.
"""

from fastapi import APIRouter, BackgroundTasks, Body, Depends, File, HTTPException, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import logging

from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import EmailVerificationRequiredError
from app.dependencies.audit import get_audit_context
from app.core.roles import available_roles
from app.dependencies.auth import CurrentSession, get_current_session, get_current_user
from app.models.user import User
from app.schemas.auth import (
    EmailVerificationRequest,
    ForgotPasswordRequest,
    GoogleAuthRequest,
    LoginRequest,
    LogoutRequest,
    RefreshTokenRequest,
    RegisterRequest,
    RegisterResponse,
    ResendVerificationRequest,
    ResetPasswordRequest,
    ResetTokenInfo,
    SelectRoleRequest,
    SignInResult,
    SkipResetRequest,
    Token,
)
from app.schemas.user import (
    ChangePasswordRequest,
    UserProfileResponse,
    UserProfileUpdate,
)
from app.schemas.ai_provider import (
    AIProviderConfigResponse,
    AIProviderConfigUpdate,
    AIProviderTestRequest,
    AIProviderTestResult,
)
from app.services.ai import provider as ai_provider_service
from app.services import auth as auth_service
from app.services import audit
from app.services import email_verification as email_verification_service
from app.services import profile as profile_service
from app.services.audit import AuditAction, AuditContext, AuditResource
from app.services.google_auth import GoogleAuthError

logger = logging.getLogger(__name__)

router = APIRouter()

# Optional bearer: select-role accepts either a selection token or a session.
_optional_bearer = HTTPBearer(auto_error=False)

SIGN_IN_DOC = (
    " Returns a session, or — for accounts with several workspaces — "
    "`requires_role_selection: true` with a short-lived `selection_token` to "
    "exchange at `POST /api/auth/select-role`."
)


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
    audit_ctx: AuditContext = Depends(get_audit_context),
) -> RegisterResponse:
    """Initiate two-phase HR registration.

    Stores the registration details in `pending_registrations` and emails a
    secure verification link and code. No permanent account is created in
    `users` and zero session tokens are issued until email verification succeeds.

    The pending row is persisted even when the email provider rejects the
    message, so the response reports `verification_email_sent: false` (with a
    safe `email_delivery_error`) rather than a 502: the registration itself was
    accepted and can be completed by requesting a new code.

    Errors:
    * 400 — the email is already registered
    * 403 — an administrator has switched registration off
    """
    try:
        pending, delivery = auth_service.initiate_registration(db, payload, audit_ctx)
    except auth_service.RegistrationDisabledError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    return RegisterResponse(
        message=(
            "Please check your email to complete registration."
            if delivery.success
            else "We couldn't send the verification email. Request a new code to try again."
        ),
        email=pending.email,
        requires_verification=True,
        verification_email_sent=delivery.success,
        email_delivery_error=delivery.error if not delivery.success else None,
    )


@router.post("/login", response_model=SignInResult, description="Sign in with email and password." + SIGN_IN_DOC)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
    audit_ctx: AuditContext = Depends(get_audit_context),
) -> Token:
    """Authenticate credentials and return an access token."""
    user = auth_service.authenticate_user(db, payload.email, payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    # An unverified account must confirm its email before it can enter the HR
    # panel; the frontend redirects to the verification screen.
    if not user.is_email_verified:
        raise EmailVerificationRequiredError(
            "Please verify your email before logging in."
        )
    auth_service.record_sign_in(db, user, "password", audit_ctx)
    return auth_service.begin_session(user)


@router.post("/google", response_model=SignInResult)
async def google_login(
    payload: GoogleAuthRequest,
    db: Session = Depends(get_db),
    audit_ctx: AuditContext = Depends(get_audit_context),
) -> Token:
    """Sign in with a Google authorization ``code``.

    The frontend (`@react-oauth/google`, auth-code flow) sends the one-time
    code plus the ``redirect_uri`` it was issued against; this endpoint
    exchanges it server-side, creates/links the local account and returns the
    application's standard JWT access token.

    Error mapping (never a bare ``401`` for a flow failure):
    * 400 — the code/redirect_uri was rejected by Google (with Google's own
      ``error_description`` when available) or the OAuth config is broken.
    * 400 — the resolved account is deactivated / unresolvable.
    * 500 — anything unexpected, logged with a full traceback.
    """
    logger.info(
        "POST /auth/google: code=…%s redirect_uri=%r",
        payload.code[-6:] if payload.code else "<empty>",
        payload.redirect_uri,
    )
    try:
        return await auth_service.login_with_google(
            db, payload.code, redirect_uri=payload.redirect_uri, context=audit_ctx
        )
    except GoogleAuthError as exc:
        # Flow-level failure (bad/expired code, redirect_uri mismatch, network,
        # misconfiguration). Descriptive 400 instead of a blanket 401.
        logger.warning("Google sign-in failed: %s", exc)
        logger.exception("Google sign-in traceback (GoogleAuthError)")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except auth_service.RegistrationDisabledError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        logger.warning("Google sign-in rejected for account reasons: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except Exception as exc:  # noqa: BLE001 — last-resort guard with full trace
        logger.exception("Unexpected failure in POST /auth/google")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google sign-in failed unexpectedly. Please try again.",
        ) from exc


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    payload: LogoutRequest | None = Body(default=None),
    db: Session = Depends(get_db),
    session: CurrentSession = Depends(get_current_session),
    audit_ctx: AuditContext = Depends(get_audit_context),
) -> None:
    """End the session.

    The presented access token is revoked (and the refresh token, when sent
    in the body), so the session and its workspace cannot be resumed; the
    client discards both. Signing in again starts over, including the
    workspace choice for accounts that have several.
    """
    current_user = session.user
    auth_service.logout(current_user, session.payload, payload.refresh_token if payload else None)
    audit.record(
        db,
        AuditAction.LOGOUT,
        resource_type=AuditResource.USER,
        resource_id=current_user.id,
        actor=current_user,
        context=audit_ctx,
    )
    return None


@router.post(
    "/verify-email",
    response_model=SignInResult,
    summary="Confirm an HR email and complete registration",
)
def verify_email(
    payload: EmailVerificationRequest,
    db: Session = Depends(get_db),
    audit_ctx: AuditContext = Depends(get_audit_context),
) -> SignInResult:
    """Confirm an HR registration with either the emailed link token or 6-digit code.

    Atomically creates the permanent user in `users`, sets is_email_verified = True,
    consumes the pending registration, and issues the legitimate access/refresh tokens.

    Errors:
    * 400 — invalid, expired or already-used credential
    * 400 — the email is already verified
    """
    try:
        user = auth_service.verify_email(
            db,
            token=payload.token,
            email=str(payload.email) if payload.email else None,
            code=payload.code,
            audit_ctx=audit_ctx,
        )
    except email_verification_service.InvalidVerificationCode as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message
        ) from exc
    except email_verification_service.EmailAlreadyVerified as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message
        ) from exc
    auth_service.record_sign_in(db, user, "email_verification", audit_ctx)
    return auth_service.begin_session(user)


@router.post("/resend-verification-code")
def resend_verification_code(
    payload: ResendVerificationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Email a fresh 6-digit verification code.

    The answer is generic for unknown/unverified addresses so it never reveals
    account existence; already-verified addresses get a clear safe message.
    Throttled per address (429 when asked again too soon or too often).

    The credentials are regenerated synchronously, then the message is handed
    to a FastAPI background task so the response never waits on the provider.
    """
    try:
        job = auth_service.prepare_resend_verification(db, str(payload.email))
    except email_verification_service.EmailAlreadyVerified as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message
        ) from exc
    except email_verification_service.ResendThrottledError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=exc.message
        ) from exc
    if job is not None:
        background_tasks.add_task(auth_service.dispatch_registration_email, *job)
    return {"message": email_verification_service.CODE_SENT_MESSAGE}


@router.post("/forgot-password")
def forgot_password(
    payload: ForgotPasswordRequest, db: Session = Depends(get_db)
) -> dict[str, str]:
    """Request a password reset for an email address.

    Generates a short-lived reset token and delivers a reset link by email (in
    development the link is written to the server log). Unknown addresses, and
    Google-only accounts, get exactly the same response, so the endpoint never
    confirms whether an email is registered.
    """
    auth_service.send_reset_email(db, payload.email)
    return {"message": "If that email exists, a reset link has been sent"}


@router.post("/verify-reset-token", response_model=ResetTokenInfo)
def verify_reset_token(
    payload: SkipResetRequest, db: Session = Depends(get_db)
) -> ResetTokenInfo:
    """Describe the account behind a reset link so the page can adapt its UX.

    Tells the frontend whether the account already has a local password and
    whether it is linked to Google, which is how the reset page can say "set a
    password for your Google account" instead of "change your password".
    """
    try:
        return auth_service.describe_reset_token(db, payload.token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@router.post("/reset-password", response_model=SignInResult)
def reset_password(
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
    audit_ctx: AuditContext = Depends(get_audit_context),
) -> Token:
    """Reset a password using the token from the reset email.

    On success the new password is hashed, sessions issued before the change are
    invalidated, and a fresh access/refresh pair is returned so the client can
    sign the user in immediately.
    """
    try:
        return auth_service.reset_password(
            db, payload.token, payload.new_password, context=audit_ctx
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@router.post("/skip-reset", response_model=SignInResult)
def skip_reset(
    payload: SkipResetRequest,
    db: Session = Depends(get_db),
    audit_ctx: AuditContext = Depends(get_audit_context),
) -> Token:
    """Keep the current password and turn the reset link into a live session.

    Backs the "Skip" button: the reset token is validated, the password is left
    untouched, and a fresh access/refresh pair is returned.
    """
    try:
        return auth_service.skip_reset(db, payload.token, context=audit_ctx)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@router.post("/refresh", response_model=Token)
def refresh(payload: RefreshTokenRequest, db: Session = Depends(get_db)) -> Token:
    """Exchange a refresh token for a new access/refresh pair.

    The presented refresh token is single-use; replaying it fails with a 401,
    which the API client answers by sending the user back to the login page.
    """
    try:
        return auth_service.refresh_access_token(db, payload.refresh_token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
# ---------------------------------------------------------------------------
# Authenticated user's own profile (Settings page)
# ---------------------------------------------------------------------------


@router.post(
    "/select-role",
    response_model=Token,
    summary="Choose the session's workspace (HR or admin)",
    description=(
        "With `selection_token` (from a sign-in that returned "
        "`requires_role_selection`): finish signing in. Without it: switch the "
        "workspace of the current bearer session, whose access token is revoked. "
        "The requested role is honoured only if the account really has it (403 "
        "otherwise); an invalid/expired selection token gives 401."
    ),
)
def select_role(
    payload: SelectRoleRequest,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(_optional_bearer),
    audit_ctx: AuditContext = Depends(get_audit_context),
) -> Token:
    try:
        if payload.selection_token:
            return auth_service.select_role(db, payload.selection_token, payload.role, audit_ctx)
        # Switching: a normal session is required (raises 401 otherwise).
        session = get_current_session(db=db, credentials=credentials)
        return auth_service.switch_role(db, session.user, session.payload, payload.role, audit_ctx)
    except auth_service.RoleNotAvailableError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def _profile(user: User, session: CurrentSession) -> UserProfileResponse:
    """Own profile plus the session's workspace information."""
    return UserProfileResponse.model_validate(user).model_copy(
        update={
            "available_roles": [role.value for role in available_roles(user)],
            "active_role": session.role.value,
        }
    )


@router.get("/me", response_model=UserProfileResponse)
def get_my_profile(session: CurrentSession = Depends(get_current_session)) -> UserProfileResponse:
    """Return the authenticated user's own profile and session workspace.

    The user is resolved from the JWT, never from a request-supplied id, so
    this can only ever return the caller's own account.
    """
    return _profile(session.user, session)


@router.patch("/me", response_model=UserProfileResponse)
def update_my_profile(
    payload: UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    """Update the authenticated user's own name/email.

    Both fields are optional; only the submitted ones are changed. The account
    is resolved from the JWT, so a client-supplied ``user_id`` is meaningless
    here and no other user can ever be modified.

    Errors:
    * 400 — the new email already belongs to another account
    * 422 — empty name, invalid email
    """
    try:
        return profile_service.update_profile(db, current_user, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@router.patch("/me/password", response_model=Token)
def change_my_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    session: CurrentSession = Depends(get_current_session),
    audit_ctx: AuditContext = Depends(get_audit_context),
) -> Token:
    """Change the authenticated user's own password.

    Requires the current password. On success every previously issued session
    is revoked and a fresh access/refresh pair is returned so the client can
    stay signed in.

    Errors:
    * 400 — no local password (Google-only account) or wrong current password
    * 422 — missing/over-long new password
    """
    try:
        return auth_service.change_password(
            db,
            session.user,
            payload.current_password,
            payload.new_password,
            context=audit_ctx,
            role=session.role,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@router.post("/me/profile-image", response_model=UserProfileResponse)
async def upload_my_profile_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    """Upload or replace the authenticated user's own profile image.

    Accepts multipart/form-data with a ``file`` field (JPG, PNG or WEBP, at
    most ``PROFILE_IMAGE_MAX_SIZE_MB`` MB). The image is validated by content
    (not just the filename), stored under a fresh UUID name and served from
    the ``/uploads`` static mount.

    Errors:
    * 400 — unsupported file type, mismatched content, or oversized upload
    """
    content = await file.read()
    try:
        return profile_service.save_profile_image(
            db,
            current_user,
            content,
            content_type=file.content_type,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@router.delete("/me/profile-image", response_model=UserProfileResponse)
def remove_my_profile_image(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    """Remove the authenticated user's own profile image.

    When no image is set the request still succeeds (nothing to remove).
    """
    return profile_service.remove_profile_image(db, current_user)


# ---------------------------------------------------------------------------
# Settings -> "Connect your provider and API key"
# ---------------------------------------------------------------------------
# Always the caller's own configuration (resolved from the JWT). Responses
# never contain the API key, only a masked hint of its last characters.


@router.get("/me/ai-provider", response_model=AIProviderConfigResponse)
def get_my_ai_provider(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AIProviderConfigResponse:
    """Return which AI provider the user's analyses use (no secrets)."""
    return ai_provider_service.get_status(db, current_user.id)


@router.put("/me/ai-provider", response_model=AIProviderConfigResponse)
def save_my_ai_provider(
    payload: AIProviderConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AIProviderConfigResponse:
    """Save the user's provider, model and (encrypted) API key.

    Errors:
    * 422 — invalid provider/model/key, or no key for a new provider
    * 503 — the server has no encryption key configured
    """
    try:
        return ai_provider_service.save_config(db, current_user.id, payload)
    except ai_provider_service.AIProviderSettingsError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.delete("/me/ai-provider", response_model=AIProviderConfigResponse)
def delete_my_ai_provider(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AIProviderConfigResponse:
    """Remove the user's provider; analyses use the platform provider again."""
    return ai_provider_service.delete_config(db, current_user.id)


@router.post("/me/ai-provider/test", response_model=AIProviderTestResult)
async def test_my_ai_provider(
    payload: AIProviderTestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AIProviderTestResult:
    """Check credentials with one small provider request, without saving."""
    try:
        return await ai_provider_service.test_connection(db, current_user.id, payload)
    except ai_provider_service.AIProviderSettingsError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
