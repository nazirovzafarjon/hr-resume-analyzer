"""SQLAlchemy models.

Importing the models here makes them visible to Alembic for autogenerate.
"""

from app.models.ai_analysis_run import AIAnalysisRun
from app.models.ai_provider_config import UserAIProviderConfig
from app.models.application_form import ApplicationForm, ApplicationResponse
from app.models.audit_log import AuditLog
from app.models.contact_message import ContactMessage
from app.models.interview import Interview
from app.models.job import Job
from app.models.platform_settings import PlatformSettings
from app.models.system_error import SystemErrorLog
from app.models.token_revocation import RevokedToken, SessionCutoff
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
    "UserAIProviderConfig",
    "AIAnalysisRun",
    "AuditLog",
    "PlatformSettings",
    "SystemErrorLog",
    "RevokedToken",
    "SessionCutoff",
    "AnalysisBatch",
    "AnalysisBatchStatus",
    "AnalysisStatus",
    "ApplicationStatus",
    "HiringStatus",
    "InterviewStatus",
]