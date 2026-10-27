"""Pydantic schemas for authentication (login / register / token)."""

from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.core.roles import SessionRole


class Token(BaseModel):
    """JWT access token returned after login, plus the paired refresh token.

    ``refresh_token`` is optional so that responses produced by code paths that
    predate the refresh flow (and the documented examples) stay valid.
    """

    access_token: str
    token_type: str = "bearer"
    refresh_token: str | None = None
    #: The workspace this session was signed for. Informational for the UI;
    #: the authoritative copy is the signed ``role`` claim inside the token.
    active_role: SessionRole = SessionRole.USER
    #: Always false here; lets clients tell a session from RoleSelectionRequired.
    requires_role_selection: Literal[False] = False
    #: Whether the account's email is confirmed. When false the panel endpoints
    #: answer 403 ``EMAIL_VERIFICATION_REQUIRED``: the UI must send the user to
    #: the verification screen instead of the dashboard.
    is_email_verified: bool = True
    requires_email_verification: bool = False
    verification_email_sent: bool = True
    email_delivery_error: str | None = None


class RoleSelectionRequired(BaseModel):
    """Returned instead of a session when the account has several workspaces.

    ``selection_token`` is short-lived, single-use and accepted only by
    ``POST /api/auth/select-role``; it cannot call any other endpoint.
    """

    requires_role_selection: Literal[True] = True
    selection_token: str
    available_roles: list[SessionRole]
    full_name: str
    expires_in: int  # seconds


#: What every sign-in endpoint returns: a session, or a workspace choice.
SignInResult = Token | RoleSelectionRequired


class SelectRoleRequest(BaseModel):
    """Choose the session's workspace.

    * With ``selection_token``: finish a sign-in that required a choice.
    * Without it: switch the workspace of the current (bearer) session.
    """

    role: SessionRole
    selection_token: str | None = Field(default=None, min_length=1)


class LogoutRequest(BaseModel):
    """Optional logout body: the refresh token to revoke with the session."""

    refresh_token: str | None = None


class LoginRequest(BaseModel):
    """Credentials for logging in."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class RegisterRequest(BaseModel):
    """Payload for HR registration."""

    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=72)


class RegisterResponse(BaseModel):
    """Response returned upon initiating HR registration (two-phase).

    Zero access or refresh tokens are returned until email verification succeeds.
    """

    message: str = "Please verify your email to complete registration."
    email: EmailStr
    requires_verification: Literal[True] = True
    verification_email_sent: bool = True
    email_delivery_error: str | None = None


class ForgotPasswordRequest(BaseModel):
    """Payload to request a password reset."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Payload to actually reset the password.

    ``token`` is the credential carried by the emailed reset link; the endpoint
    answers with a fresh access/refresh pair so the user is signed in straight
    after the change.
    """

    token: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=72)


class SkipResetRequest(BaseModel):
    """Payload for the "Skip" option on the reset page.

    Same token as :class:`ResetPasswordRequest`, but the password is left
    untouched and only the session is (re-)issued.
    """

    token: str = Field(min_length=1)


class RefreshTokenRequest(BaseModel):
    """Payload for exchanging a refresh token for a new access token."""

    refresh_token: str = Field(min_length=1)


class ResetTokenInfo(BaseModel):
    """Account facts describing a reset link, for rendering the reset page.

    Returned only to a caller that already presents a valid, unexpired reset
    token, so it never widens account enumeration beyond the emailed link.
    """

    email: EmailStr
    full_name: str
    has_password: bool
    is_google_account: bool


class EmailVerificationRequest(BaseModel):
    """Confirm an HR email with either the emailed verification link token or 6-digit code."""

    token: str | None = Field(default=None, min_length=1)
    email: EmailStr | None = None
    code: str | None = Field(default=None, min_length=6, max_length=6, pattern=r"^\d{6}$")


class ResendVerificationRequest(BaseModel):
    """Request a fresh verification code for an address (public endpoint)."""

    email: EmailStr


class VerifyEmailTokenRequest(BaseModel):
    """Candidate Portal verification link credential (``?token=...``)."""

    token: str = Field(min_length=1)


class GoogleAuthRequest(BaseModel):
    """Payload to sign in with Google.

    Carries the one-time authorization ``code`` obtained by the frontend
    (``@react-oauth/google`` auth-code flow) plus the ``redirect_uri`` that
    the code was issued against. The backend exchanges it for Google tokens
    and creates/links the user account.

    ``redirect_uri`` is optional:
    * ``"postmessage"`` — the code came from Google's JS popup flow
      (``useGoogleLogin`` default), which always binds codes to postmessage.
    * Absent / the configured callback URL — the code came from the full-page
      redirect flow (``/oauth/callback``).
    """

    code: str = Field(min_length=1)
    redirect_uri: str | None = None