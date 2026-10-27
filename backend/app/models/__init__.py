"""SQLAlchemy models.

Importing the models here makes them visible to Alembic for autogenerate.
"""

from app.models.ai_analysis_run import AIAnalysisRun
from app.models.ai_provider_config import UserAIProviderConfig
from app.models.analysis_batch import AnalysisBatch, AnalysisBatchStatus
from app.models.application import (
    AnalysisStatus,
    Application,
    ApplicationStatus,
    HiringStatus,
    InterviewStatus,
)
from app.models.application_form import ApplicationForm, ApplicationResponse
from app.models.application_status_history import ApplicationStatusHistory
from app.models.audit_log import AuditLog
from app.models.candidate_account import CandidateAccount
from app.models.contact_message import ContactMessage
from app.models.email_verification import EmailVerification
from app.models.interview import Interview
from app.models.job import Job
from app.models.platform_settings import PlatformSettings
from app.models.system_error import SystemErrorLog
from app.models.pending_registration import PendingRegistration
from app.models.token_revocation import RevokedToken, SessionCutoff
from app.models.user import User

__all__ = [
    "PendingRegistration",
    "User",
    "Job",
    "Application",
    "ApplicationStatusHistory",
    "CandidateAccount",
    "Interview",
    "ApplicationForm",
    "ApplicationResponse",
    "ContactMessage",
    "EmailVerification",
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