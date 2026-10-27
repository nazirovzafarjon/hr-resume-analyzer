"""Candidate Portal API (``/api/candidate/*``).

Security boundary
-----------------
* Every endpoint except the sign-in ones depends on ``get_current_candidate``,
  which accepts only ``candidate_access`` tokens (HR tokens get 401 here, and
  candidate tokens get 401 on every HR endpoint).
* Every query is scoped to the authenticated account's id. Another
  candidate's application or interview answers exactly like a missing one
  (404), so ids cannot be probed.
* Responses are explicit candidate schemas: no HR recommendation, interviewer
  notes, internal AI text, job owner or other applicants.

Endpoints
---------
POST  /candidate/auth/register | login | refresh | logout
POST  /candidate/auth/forgot-password | reset-password
GET   /candidate/profile, PATCH /candidate/profile
PATCH /candidate/profile/password
POST  /candidate/profile/image, DELETE /candidate/profile/image
GET   /candidate/dashboard
GET   /candidate/applications, GET /candidate/applications/{id}
GET   /candidate/applications/{id}/resume
GET   /candidate/interviews, GET /candidate/interviews/{id}

Applying goes through the existing public form
(``POST /api/public/applications/{token}/submit``); sent with a candidate
token, the application is linked to the account.
"""

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import TOKEN_PURPOSE_CANDIDATE_ACCESS, decode_token_for_purpose
from app.crud import candidate_account as candidate_crud
from app.dependencies.candidate_auth import get_current_candidate
from app.models.candidate_account import CandidateAccount
from app.schemas.auth import GoogleAuthRequest, VerifyEmailTokenRequest
from app.schemas.candidate import (
    CandidateApplicationDetail,
    CandidateApplicationSummary,
    CandidateAuthResult,
    CandidateDashboard,
    CandidateForgotPasswordRequest,
    CandidateInterview,
    CandidateLoginRequest,
    CandidateLogoutRequest,
    CandidatePasswordChange,
    CandidateProfile,
    CandidateProfileUpdate,
    CandidateRefreshRequest,
    CandidateRegisterRequest,
    CandidateResetPasswordRequest,
    CandidateTokens,
)
from app.services import candidate_auth
from app.services import candidate_portal
from app.services import profile as profile_service
from app.services import resume_file as resume_file_service
from app.services.google_auth import GoogleAuthError

logger = logging.getLogger(__name__)

router = APIRouter()

_bearer_scheme = HTTPBearer(auto_error=False)


def _profile(candidate: CandidateAccount) -> CandidateProfile:
    return CandidateProfile(
        id=candidate.id,
        email=candidate.email,
        full_name=candidate.full_name,
        phone=candidate.phone,
        profile_image=candidate.profile_image,
        created_at=candidate.created_at,
        has_password=candidate.has_password,
        is_email_verified=candidate.is_email_verified,
    )


def _auth_result(candidate: CandidateAccount, tokens: CandidateTokens) -> CandidateAuthResult:
    return CandidateAuthResult(**tokens.model_dump(), candidate=_profile(candidate))


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


@router.post("/auth/register", response_model=CandidateAuthResult, status_code=status.HTTP_201_CREATED)
def register(payload: CandidateRegisterRequest, db: Session = Depends(get_db)) -> CandidateAuthResult:
    """Create a candidate account and sign it in."""
    try:
        candidate = candidate_auth.register(
            db,
            email=str(payload.email),
            full_name=payload.full_name,
            password=payload.password,
            phone=payload.phone,
        )
    except candidate_auth.DuplicateEmailError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _auth_result(candidate, candidate_auth.issue_tokens(candidate))


@router.post("/auth/login", response_model=CandidateAuthResult)
def login(payload: CandidateLoginRequest, db: Session = Depends(get_db)) -> CandidateAuthResult:
    """Sign in with email and password (401 for wrong credentials or a deactivated account)."""
    try:
        candidate = candidate_auth.authenticate(db, str(payload.email), payload.password)
    except candidate_auth.CandidateAuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return _auth_result(candidate, candidate_auth.issue_tokens(candidate))


@router.post("/auth/google", response_model=CandidateAuthResult)
async def google_login(
    payload: GoogleAuthRequest,
    db: Session = Depends(get_db),
) -> CandidateAuthResult:
    """Sign in or register a candidate with a Google authorization ``code``."""
    try:
        candidate = await candidate_auth.login_with_google(
            db, payload.code, redirect_uri=payload.redirect_uri
        )
        return _auth_result(candidate, candidate_auth.issue_tokens(candidate))
    except GoogleAuthError as exc:
        logger.warning("Candidate Google sign-in failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except candidate_auth.CandidateAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected failure in POST /candidate/auth/google")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google sign-in failed unexpectedly. Please try again.",
        ) from exc


@router.post("/auth/verify-email", response_model=CandidateAuthResult)
def verify_email(payload: VerifyEmailTokenRequest, db: Session = Depends(get_db)) -> CandidateAuthResult:
    """Confirm a candidate email from the verification link and sign them in."""
    try:
        candidate = candidate_auth.verify_email(db, payload.token)
    except candidate_auth.CandidateAuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _auth_result(candidate, candidate_auth.issue_tokens(candidate))


@router.post("/auth/resend-verification")
def resend_verification(payload: CandidateForgotPasswordRequest, db: Session = Depends(get_db)) -> dict:
    """Email a fresh candidate verification link (generic, throttled)."""
    try:
        candidate_auth.resend_verification_email(db, str(payload.email))
    except candidate_auth.ResendThrottledError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=exc.message
        ) from exc
    return {"message": candidate_auth.EMAIL_VERIFICATION_SENT_MESSAGE}


@router.post("/auth/refresh", response_model=CandidateTokens)
def refresh(payload: CandidateRefreshRequest, db: Session = Depends(get_db)) -> CandidateTokens:
    """Exchange a candidate refresh token for a new pair (single use)."""
    try:
        return candidate_auth.refresh(db, payload.refresh_token)
    except candidate_auth.CandidateAuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    payload: CandidateLogoutRequest | None = None,
    db: Session = Depends(get_db),
    candidate: CandidateAccount = Depends(get_current_candidate),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> None:
    """Revoke the current access token (and the refresh token when sent)."""
    try:
        access_payload = decode_token_for_purpose(credentials.credentials, TOKEN_PURPOSE_CANDIDATE_ACCESS)
    except (JWTError, AttributeError):  # already validated by the dependency
        return None
    candidate_auth.logout(db, access_payload, payload.refresh_token if payload else None)
    return None


@router.post("/auth/forgot-password")
def forgot_password(payload: CandidateForgotPasswordRequest, db: Session = Depends(get_db)) -> dict:
    """Email a reset link. Same answer for every address (no account enumeration)."""
    candidate_auth.send_reset_email(db, str(payload.email))
    return {"message": "If an account exists for this email, a reset link has been sent."}


@router.post("/auth/reset-password", response_model=CandidateAuthResult)
def reset_password(payload: CandidateResetPasswordRequest, db: Session = Depends(get_db)) -> CandidateAuthResult:
    """Set a new password from the emailed link and sign in."""
    try:
        candidate, tokens = candidate_auth.reset_password(db, payload.token, payload.new_password)
    except candidate_auth.CandidateAuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _auth_result(candidate, tokens)


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------


@router.get("/profile", response_model=CandidateProfile)
def get_profile(candidate: CandidateAccount = Depends(get_current_candidate)) -> CandidateProfile:
    return _profile(candidate)


@router.patch("/profile", response_model=CandidateProfile)
def update_profile(
    payload: CandidateProfileUpdate,
    db: Session = Depends(get_db),
    candidate: CandidateAccount = Depends(get_current_candidate),
) -> CandidateProfile:
    """Update name, email and phone (409 when the email belongs to another candidate)."""
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("full_name") is None:
        changes.pop("full_name", None)
    if "email" in changes:
        if changes["email"] is None:
            changes.pop("email")
        else:
            changes["email"] = str(changes["email"]).strip().lower()
            other = candidate_crud.get_by_email(db, changes["email"])
            if other is not None and other.id != candidate.id:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists.")
    try:
        candidate = candidate_crud.update(db, candidate, changes)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists.") from exc
    return _profile(candidate)


@router.patch("/profile/password", response_model=CandidateTokens)
def change_password(
    payload: CandidatePasswordChange,
    db: Session = Depends(get_db),
    candidate: CandidateAccount = Depends(get_current_candidate),
) -> CandidateTokens:
    """Change the password; other sessions are signed out, this one gets a fresh pair."""
    try:
        return candidate_auth.change_password(db, candidate, payload.current_password, payload.new_password)
    except candidate_auth.CandidateAuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/profile/image", response_model=CandidateProfile)
async def upload_profile_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    candidate: CandidateAccount = Depends(get_current_candidate),
) -> CandidateProfile:
    """Upload or replace the profile image (same validation as HR users)."""
    content = await file.read()
    try:
        new_path = profile_service.store_profile_image(content, file.content_type)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    old_path = candidate.profile_image
    candidate = candidate_crud.update(db, candidate, {"profile_image": new_path})
    if old_path:
        profile_service.delete_profile_image_file(old_path)
    return _profile(candidate)


@router.delete("/profile/image", response_model=CandidateProfile)
def remove_profile_image(
    db: Session = Depends(get_db),
    candidate: CandidateAccount = Depends(get_current_candidate),
) -> CandidateProfile:
    old_path = candidate.profile_image
    if old_path:
        candidate = candidate_crud.update(db, candidate, {"profile_image": None})
        profile_service.delete_profile_image_file(old_path)
    return _profile(candidate)


# ---------------------------------------------------------------------------
# Dashboard, applications, interviews (own data only)
# ---------------------------------------------------------------------------


@router.get("/dashboard", response_model=CandidateDashboard)
def get_dashboard(
    db: Session = Depends(get_db),
    candidate: CandidateAccount = Depends(get_current_candidate),
) -> CandidateDashboard:
    return candidate_portal.dashboard(db, candidate)


@router.get("/applications", response_model=list[CandidateApplicationSummary])
def list_applications(
    db: Session = Depends(get_db),
    candidate: CandidateAccount = Depends(get_current_candidate),
) -> list[CandidateApplicationSummary]:
    return candidate_portal.list_applications(db, candidate)


def _own_application(db: Session, candidate: CandidateAccount, application_id: int):
    application = candidate_portal.get_application(db, candidate, application_id)
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return application


@router.get("/applications/{application_id}", response_model=CandidateApplicationDetail)
def get_application(
    application_id: int,
    db: Session = Depends(get_db),
    candidate: CandidateAccount = Depends(get_current_candidate),
) -> CandidateApplicationDetail:
    """Job, answers, safe AI feedback, timeline and interviews of one own application."""
    return candidate_portal.application_detail(_own_application(db, candidate, application_id))


@router.get("/applications/{application_id}/resume", response_class=FileResponse)
def get_application_resume(
    application_id: int,
    db: Session = Depends(get_db),
    candidate: CandidateAccount = Depends(get_current_candidate),
) -> FileResponse:
    """Download the CV the candidate submitted with their own application."""
    application = _own_application(db, candidate, application_id)
    try:
        resume = resume_file_service.get_resume_file(application)
    except resume_file_service.ResumeUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    return FileResponse(
        resume.path,
        media_type=resume.media_type,
        filename=resume.filename,
        content_disposition_type="attachment",
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.get("/interviews", response_model=list[CandidateInterview])
def list_interviews(
    db: Session = Depends(get_db),
    candidate: CandidateAccount = Depends(get_current_candidate),
) -> list[CandidateInterview]:
    return candidate_portal.list_interviews(db, candidate)


@router.get("/interviews/{interview_id}", response_model=CandidateInterview)
def get_interview(
    interview_id: int,
    db: Session = Depends(get_db),
    candidate: CandidateAccount = Depends(get_current_candidate),
) -> CandidateInterview:
    interview = candidate_portal.get_interview(db, candidate, interview_id)
    if interview is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found")
    return interview
