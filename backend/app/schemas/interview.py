"""Pydantic schemas for interviews.

Interviews are plain HR-entered records: fields are validated for shape only,
the ``meeting_link`` is a free-form string that HR pastes from Zoom/Google Meet.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.interview import InterviewStatus


class InterviewBase(BaseModel):
    """Common interview fields."""

    interviewer: str = Field(min_length=1, max_length=255)
    scheduled_at: datetime
    duration_minutes: int = Field(default=60, ge=5, le=480)
    status: InterviewStatus = InterviewStatus.UPCOMING
    meeting_link: str | None = Field(default=None, max_length=1024)
    notes: str | None = None


class InterviewCreate(InterviewBase):
    """Payload for scheduling a new interview for a candidate."""

    candidate_id: int


class InterviewUpdate(BaseModel):
    """Fields that can be updated on an interview (all optional).

    Mirrors ``InterviewBase``: interviewer must not be an empty string.
    """

    candidate_id: int | None = None
    interviewer: str | None = Field(default=None, min_length=1, max_length=255)
    scheduled_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=5, le=480)
    status: InterviewStatus | None = None
    meeting_link: str | None = Field(default=None, max_length=1024)
    notes: str | None = None


class InterviewResponse(InterviewBase):
    """Interview data returned to clients, enriched with candidate context."""

    id: int
    candidate_id: int
    hr_id: int
    job_id: int
    candidate_name: str
    job_title: str
    company_name: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InterviewStats(BaseModel):
    """Counts of interviews grouped by status, for the metric cards."""

    total: int
    upcoming: int
    completed: int
    cancelled: int