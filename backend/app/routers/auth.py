"""Authentication API endpoints.

Register, login, logout, forgot/reset password.
"""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

import logging

from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    GoogleAuthRequest,
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    ResetPasswordRequest,
    ResetTokenInfo,
    SkipResetRequest,
    Token,
)
from app.schemas.user import (
    ChangePasswordRequest,
    UserProfileResponse,
    UserProfileUpdate,
)
from app.services import auth as auth_service
from app.services import settings as settings_service
from app.services.google_auth import GoogleAuthError

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/register",
    response_model=Token,
    status_code=status.HTTP_201_CREATED,
)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> Token:
    """Create a new HR account and return a fresh access token."""
    try:
        user = auth_service.register_user(db, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return auth_service.issue_token(user)


@router.post("/login", response_model=Token)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> Token:
    """Authenticate credentials and return an access token."""
    user = auth_service.authenticate_user(db, payload.email, payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    return auth_service.issue_token(user)


@router.post("/google", response_model=Token)
async def google_login(
    payload: GoogleAuthRequest, db: Session = Depends(get_db)
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
            db, payload.code, redirect_uri=payload.redirect_uri
        )
    except GoogleAuthError as exc:
        # Flow-level failure (bad/expired code, redirect_uri mismatch, network,
        # misconfiguration). Descriptive 400 instead of a blanket 401.
        logger.warning("Google sign-in failed: %s", exc)
        logger.exception("Google sign-in traceback (GoogleAuthError)")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
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
def logout(current_user: User = Depends(get_current_user)) -> None:
    """Invalidate the client session.

    JWT tokens are stateless, so logging out simply asks the client to
    discard its token; the endpoint exists to trigger that client-side.
    """
    return None


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


@router.post("/reset-password", response_model=Token)
def reset_password(
    payload: ResetPasswordRequest, db: Session = Depends(get_db)
) -> Token:
    """Reset a password using the token from the reset email.

    On success the new password is hashed, sessions issued before the change are
    invalidated, and a fresh access/refresh pair is returned so the client can
    sign the user in immediately.
    """
    try:
        return auth_service.reset_password(db, payload.token, payload.new_password)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@router.post("/skip-reset", response_model=Token)
def skip_reset(payload: SkipResetRequest, db: Session = Depends(get_db)) -> Token:
    """Keep the current password and turn the reset link into a live session.

    Backs the "Skip" button: the reset token is validated, the password is left
    untouched, and a fresh access/refresh pair is returned.
    """
    try:
        return auth_service.skip_reset(db, payload.token)
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


@router.get("/me", response_model=UserProfileResponse)
def get_my_profile(current_user: User = Depends(get_current_user)) -> User:
    """Return the authenticated user's own profile.

    The user is resolved from the JWT, never from a request-supplied id, so
    this can only ever return the caller's own account.
    """
    return current_user


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
        return settings_service.update_profile(db, current_user, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@router.patch("/me/password", response_model=Token)
def change_my_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
            db, current_user, payload.current_password, payload.new_password
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
        return settings_service.save_profile_image(
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
    return settings_service.remove_profile_image(db, current_user)