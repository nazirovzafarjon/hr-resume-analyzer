"""Pydantic schemas for the Candidate Portal (``/api/candidate/*``).

Every response here is built explicitly by ``services.candidate_portal`` —
never by serializing an ORM ``Application`` / ``Interview`` directly — so HR-only
fields (hiring recommendation, interviewer notes, internal AI text, owner data,
other applicants) cannot leak by accident when those models grow.
"""

import enum
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

#: Candidate passwords: at least 8 characters, at most 72 (bcrypt's limit).
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 72


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class CandidateRegisterRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)
    phone: str | None = Field(default=None, max_length=50)

    @field_validator("full_name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Full name is required")
        return value.strip()

    @field_validator("phone")
    @classmethod
    def _clean_phone(cls, value: str | None) -> str | None:
        return _clean_optional(value)


class CandidateLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)


class CandidateRefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class CandidateLogoutRequest(BaseModel):
    refresh_token: str | None = None


class CandidateForgotPasswordRequest(BaseModel):
    email: EmailStr


class CandidateResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1)
    new_password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)


class CandidatePasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)
    new_password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)


class CandidateTokens(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------


class CandidateProfile(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    phone: str | None = None
    profile_image: str | None = None
    created_at: datetime
    #: False for Google-only accounts, which have no local password. Lets the
    #: profile page hide the change-password form instead of calling it and
    #: getting a 400.
    has_password: bool = True
    #: False until the candidate confirms their email; the Candidate Portal is
    #: gated until then.
    is_email_verified: bool = True


class CandidateProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)

    @field_validator("full_name")
    @classmethod
    def _name_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Full name cannot be empty")
        return value.strip() if value is not None else None

    @field_validator("phone")
    @classmethod
    def _clean_phone(cls, value: str | None) -> str | None:
        return _clean_optional(value)


class CandidateAuthResult(CandidateTokens):
    """Tokens plus the profile, returned by register / login / reset."""

    candidate: CandidateProfile


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------


class CandidateStatus(str, enum.Enum):
    """Candidate-facing application status (derived, never stored).

    Deliberately separate from the HR ``ApplicationStatus`` (which uses
    internal terms like "shortlisted"), from the interview status and from the
    AI result. See ``services.candidate_portal.candidate_status``.
    """

    SUBMITTED = "submitted"
    AI_REVIEW = "ai_review"
    HR_REVIEW = "hr_review"
    INTERVIEW_INVITED = "interview_invited"
    INTERVIEW_SCHEDULED = "interview_scheduled"
    DECISION_PENDING = "decision_pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class CandidateAnalysisState(str, enum.Enum):
    NOT_ANALYZED = "not_analyzed"
    ANALYZING = "analyzing"
    ANALYZED = "analyzed"
    FAILED = "failed"


class CandidateInterviewState(str, enum.Enum):
    """Short interview summary for application cards."""

    NOT_SCHEDULED = "not_scheduled"
    SCHEDULED = "scheduled"
    COMPLETED = "completed"


class CandidateJob(BaseModel):
    """Presentation fields of the job applied for (already public)."""

    position: str
    company_name: str
    description: str | None = None
    required_skills: str | None = None
    required_experience: str | None = None


class CandidateAIFeedback(BaseModel):
    """Candidate-safe resume/job compatibility.

    IMPORTANT: this is intentionally a *subset* of the internal analysis:
    only the match percentage and short skill/requirement lists. The HR
    recommendation, free-text AI summaries (written for recruiters), risks,
    weaknesses and the internal ``ai_score`` are never included, and the
    provider's error text is never exposed.
    """

    state: CandidateAnalysisState
    match_percentage: int | None = None
    matched_skills: list[str] = []
    skills_to_improve: list[str] = []
    requirements_met: list[str] = []
    requirements_to_strengthen: list[str] = []
    analyzed_at: datetime | None = None


class TimelineStepState(str, enum.Enum):
    DONE = "done"
    CURRENT = "current"
    UPCOMING = "upcoming"
    SKIPPED = "skipped"
    UNAVAILABLE = "unavailable"


class TimelineStep(BaseModel):
    """One step of the application timeline.

    ``date`` is only set when the real moment is known (never guessed).
    ``outcome`` refines the final step: ``accepted`` / ``rejected`` /
    ``withdrawn``.
    """

    key: str
    state: TimelineStepState
    date: datetime | None = None
    outcome: str | None = None


class CandidateInterview(BaseModel):
    id: int
    application_id: int
    position: str
    company_name: str
    scheduled_at: datetime
    duration_minutes: int
    status: str
    is_online: bool
    # Only sent for upcoming interviews.
    meeting_link: str | None = None


class CandidateApplicationSummary(BaseModel):
    id: int
    position: str
    company_name: str
    submitted_at: datetime
    status: CandidateStatus
    analysis_state: CandidateAnalysisState
    interview_state: CandidateInterviewState
    next_interview_at: datetime | None = None


class CandidateAnswer(BaseModel):
    label: str
    type: str
    # Text answers as submitted; file fields only say whether a file is attached
    # (stored server paths are never exposed).
    value: str | list[str] | None = None
    file_attached: bool = False


class CandidateApplicationDetail(CandidateApplicationSummary):
    job: CandidateJob
    has_resume: bool
    answers: list[CandidateAnswer]
    analysis: CandidateAIFeedback
    timeline: list[TimelineStep]
    interviews: list[CandidateInterview]


class CandidateDashboard(BaseModel):
    total_applications: int
    active_applications: int
    upcoming_interviews: int
    completed_applications: int
    next_interview: CandidateInterview | None = None
    recent_applications: list[CandidateApplicationSummary]
