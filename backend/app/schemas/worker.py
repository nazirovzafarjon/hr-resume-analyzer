"""Pydantic schemas for workers/candidates (applications).

A ``Worker`` row *is* an application: the list payload is what the Applications
menu renders, the detail payload adds the submitted answers, the stored AI
analysis and the candidate's interviews. The AI-owned fields
(``ai_score``/``ai_analysis_details``/``analysis_status``) are server-managed —
they are returned to clients but never accepted from them.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.interview import InterviewStatus as InterviewSessionStatus
from app.models.worker import (
    AnalysisStatus,
    ApplicationStatus,
    HiringStatus,
    InterviewStatus,
)
from app.schemas.application_analysis import ApplicationAnalysis


class WorkerBase(BaseModel):
    """Common worker/candidate fields."""

    name: str = Field(min_length=1)
    email: str
    resume_path: str = ""


class WorkerCreate(WorkerBase):
    """Payload for recording a worker application by hand."""


class WorkerUpdate(BaseModel):
    """Fields HR may update on an application/candidate (all optional).

    Includes the HR-owned statuses only. The AI result fields are written by the
    analysis service (``POST /workers/{id}/analyze``), never by a client, and
    ``candidate_at`` is set by the convert-to-candidate endpoint.
    """

    name: str | None = None
    email: str | None = None
    resume_path: str | None = None
    application_status: ApplicationStatus | None = None
    hiring_status: HiringStatus | None = None
    interview_status: InterviewStatus | None = None
    ai_score: float | None = None
    ai_analysis_details: dict[str, Any] | None = None
    analysis_status: AnalysisStatus | None = None


class WorkerAnalyzeRequest(BaseModel):
    """Body of ``POST /workers/{id}/analyze``.

    ``force`` re-runs the analysis for an application that already has one
    ("Analyze again"). Without it an existing result is reused and the AI
    provider is not called again.
    """

    force: bool = False


# Auto-analyze batch schemas

class AutoAnalyzeAvailableResponse(BaseModel):
    """Response for GET /workers/auto-analyze/available."""

    count: int


class AutoAnalyzeStartRequest(BaseModel):
    """Request body for POST /workers/auto-analyze."""

    count: int = Field(ge=1, le=1000)
    order: str = Field(default="oldest", pattern="^(oldest|newest)$")
    job_id: int | None = None


class AutoAnalyzeStartResponse(BaseModel):
    """Response for POST /workers/auto-analyze."""

    batch_id: int
    requested_count: int
    selected_count: int
    status: str


class AutoAnalyzeProgressResponse(BaseModel):
    """Response for GET /workers/auto-analyze/{batch_id}."""

    batch_id: int
    status: str
    total: int
    processed: int
    successful: int
    failed: int
    remaining: int
    current_application_id: int | None = None
    created_at: datetime | None = None
    finished_at: datetime | None = None


class WorkerResponse(BaseModel):
    """Application/candidate row as returned by the list endpoint.

    Enriched with the owning job's company/position so the Applications list
    needs no second request; the heavy analysis payload stays in the detail
    response.
    """

    id: int
    job_id: int
    name: str
    email: str
    resume_path: str
    ai_score: float
    application_status: ApplicationStatus
    analysis_status: AnalysisStatus
    analysis_error: str | None = None
    analysis_started_at: datetime | None = None
    hiring_status: HiringStatus
    interview_status: InterviewStatus
    is_candidate: bool
    candidate_at: datetime | None = None
    created_at: datetime
    submitted_at: datetime
    company_name: str
    position: str

    model_config = ConfigDict(from_attributes=True)


class ApplicantAnswer(BaseModel):
    """One answer the applicant submitted through the public form."""

    field_id: str = ""
    key: str = ""
    label: str = ""
    type: str = ""
    value: Any = None

    model_config = ConfigDict(from_attributes=True)


class WorkerInterviewSummary(BaseModel):
    """Interview booked for a candidate (summary for the candidate page)."""

    id: int
    interviewer: str
    scheduled_at: datetime
    status: InterviewSessionStatus
    notes: str | None = None

    model_config = ConfigDict(from_attributes=True)


class WorkerDetailResponse(WorkerResponse):
    """Full application/candidate record.

    Adds the submitted form answers, a browser-usable resume URL, the analysis
    stored in PostgreSQL and the candidate's interviews. Nothing here triggers
    AI work — ``GET`` requests only read what the last analysis stored.
    """

    resume_url: str | None = None
    responses: list[ApplicantAnswer] = Field(default_factory=list)
    analysis: ApplicationAnalysis | None = None
    interviews: list[WorkerInterviewSummary] = Field(default_factory=list)