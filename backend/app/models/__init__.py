"""SQLAlchemy models.

Importing the models here makes them visible to Alembic for autogenerate.
"""

from app.models.application_form import ApplicationForm, ApplicationResponse
from app.models.contact_message import ContactMessage
from app.models.interview import Interview
from app.models.job import Job
from app.models.user import User
from app.models.worker import (
    AnalysisBatch,
    AnalysisBatchStatus,
    AnalysisStatus,
    ApplicationStatus,
    HiringStatus,
    InterviewStatus,
    Worker,
)

__all__ = [
    "User",
    "Job",
    "Worker",
    "Interview",
    "ApplicationForm",
    "ApplicationResponse",
    "ContactMessage",
    "AnalysisBatch",
    "AnalysisBatchStatus",
    "AnalysisStatus",
    "ApplicationStatus",
    "HiringStatus",
    "InterviewStatus",
]