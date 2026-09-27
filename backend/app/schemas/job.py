"""Pydantic schemas for jobs (vacancies)."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.application_form import ApplicationFormResponse, ApplicationFormPayload


class JobBase(BaseModel):
    """Common job fields."""

    company_name: str = Field(min_length=1)
    position: str = Field(min_length=1)
    description: str = ""
    required_skills: str = ""
    required_experience: str = ""


class JobCreate(JobBase):
    """Payload for creating a job.

    ``application_form`` is optional: when present, the reviewed application
    fields are validated, stored and a public application token is generated
    in the same request ("Generate Public Application Link" in the create
    flow). It is not a database column — see ``application_form`` handling in
    the router/service.
    """

    application_form: ApplicationFormPayload | None = None


class JobUpdate(BaseModel):
    """Fields that can be updated on a job.

    Mirrors ``JobBase``: company_name and position must not be empty strings.
    The application form configuration has its own dedicated endpoints
    (``/jobs/{id}/application-form``) so editing job info can never silently
    rewrite the candidate form.
    """

    company_name: str | None = Field(default=None, min_length=1)
    position: str | None = Field(default=None, min_length=1)
    description: str | None = None
    required_skills: str | None = None
    required_experience: str | None = None


class JobResponse(JobBase):
    """Job data returned to clients."""

    id: int
    public_id: uuid.UUID
    leads_count: int
    created_at: datetime
    # Present when the job has a published application form (HR-only views).
    application_form: ApplicationFormResponse | None = None

    model_config = ConfigDict(from_attributes=True)


class PublicJobSummary(JobBase):
    """Job presentation fields safe to expose without authentication.

    Deliberately excludes ``id``/``public_id``, ``leads_count`` and
    ``application_form`` (which carries the application form's secret
    ``public_token``) — none of that belongs in an unauthenticated response.
    """

    model_config = ConfigDict(from_attributes=True)


class JobAnalyzeRequest(BaseModel):
    """Request payload for AI vacancy analysis."""

    content: str = Field(min_length=1, max_length=50000)


class JobAIAnalysisResult(BaseModel):
    """Structured result from AI vacancy analysis.

    Matches the fields expected by the Job create/update endpoints.
    ``application_fields`` carries *suggestions* for the public application
    form, already normalised against the fixed field-type registry — AI
    output is data only and never reaches the public UI unchecked.
    """

    company_name: str = ""
    position: str = ""
    description: str = ""
    required_skills: str = ""
    required_experience: str = ""
    application_fields: list[dict[str, Any]] | None = None

    model_config = ConfigDict(from_attributes=True)