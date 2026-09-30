"""Audit trail: record who did what, safely.

Design decisions
----------------
* **Best effort, never blocking.** Auditing runs *after* the business change
  has been committed. If writing the audit row fails, the failure is logged
  and swallowed: a user must never see their (already saved) change reported
  as an error because of bookkeeping.
* **No secrets, no documents.** ``details`` passes through
  :func:`sanitize_details`, which drops any key that looks like a credential
  or document content and truncates long values. Callers should only pass
  identifiers, field *names*, statuses and counts in the first place.
* **Append-only.** There is no update/delete path (see ``crud.audit_log``).
* **HTTP-free services.** Request metadata (IP, user agent) travels in an
  :class:`AuditContext` built by a FastAPI dependency, so services can audit
  without importing anything from the web layer.
"""

import logging
import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.crud import audit_log as audit_crud
from app.models.user import User

logger = logging.getLogger(__name__)


class AuditAction:
    """Every action name written to ``audit_logs.action``."""

    # Authentication
    REGISTER = "REGISTER"
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    PASSWORD_CHANGE = "PASSWORD_CHANGE"
    PASSWORD_RESET = "PASSWORD_RESET"
    ROLE_SELECTED = "ROLE_SELECTED"
    ROLE_SWITCHED = "ROLE_SWITCHED"
    # Jobs
    CREATE_JOB = "CREATE_JOB"
    UPDATE_JOB = "UPDATE_JOB"
    DELETE_JOB = "DELETE_JOB"
    # Applications / candidates
    APPLICATION_RECEIVED = "APPLICATION_RECEIVED"
    CREATE_APPLICATION = "CREATE_APPLICATION"
    UPDATE_APPLICATION = "UPDATE_APPLICATION"
    DELETE_APPLICATION = "DELETE_APPLICATION"
    CONVERT_TO_CANDIDATE = "CONVERT_TO_CANDIDATE"
    # Interviews
    CREATE_INTERVIEW = "CREATE_INTERVIEW"
    UPDATE_INTERVIEW = "UPDATE_INTERVIEW"
    DELETE_INTERVIEW = "DELETE_INTERVIEW"
    # AI
    AI_ANALYSIS_COMPLETED = "AI_ANALYSIS_COMPLETED"
    AI_ANALYSIS_FAILED = "AI_ANALYSIS_FAILED"
    AI_BATCH_STARTED = "AI_BATCH_STARTED"
    # Administration
    ACTIVATE_USER = "ACTIVATE_USER"
    DEACTIVATE_USER = "DEACTIVATE_USER"
    PROMOTE_USER = "PROMOTE_USER"
    DEMOTE_USER = "DEMOTE_USER"
    UPDATE_USER = "UPDATE_USER"
    DELETE_USER = "DELETE_USER"
    UPDATE_SETTINGS = "UPDATE_SETTINGS"

    @classmethod
    def all(cls) -> list[str]:
        return sorted(
            value for key, value in vars(cls).items() if key.isupper() and isinstance(value, str)
        )


class AuditResource:
    """Values written to ``audit_logs.resource_type``."""

    USER = "user"
    JOB = "job"
    APPLICATION = "application"
    INTERVIEW = "interview"
    AI_ANALYSIS = "ai_analysis"
    SETTINGS = "settings"

    @classmethod
    def all(cls) -> list[str]:
        return sorted(
            value for key, value in vars(cls).items() if key.isupper() and isinstance(value, str)
        )


@dataclass(frozen=True)
class AuditContext:
    """Request metadata attached to an audit row (both optional)."""

    ip_address: str | None = None
    user_agent: str | None = None
    #: Correlates the entry with server logs and System Errors.
    request_id: str | None = None


# Any detail key containing one of these fragments is dropped before storage.
_SENSITIVE_KEY = re.compile(
    r"pass|secret|token|api[_-]?key|authorization|cookie|credential|resume|cv_text|content",
    re.IGNORECASE,
)
_MAX_STRING = 200
_MAX_ITEMS = 20


def _clean_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:_MAX_STRING]
    if isinstance(value, (list, tuple, set)):
        return [
            _clean_value(item)
            for item in list(value)[:_MAX_ITEMS]
            if item is None or isinstance(item, (bool, int, float, str))
        ]
    # Enums, datetimes and anything else become short strings.
    return str(getattr(value, "value", value))[:_MAX_STRING]


def sanitize_details(details: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return a flat, size-limited copy of ``details`` without sensitive keys.

    Nested dictionaries are dropped on purpose: audit details are meant to be
    a few scalar facts, and flattening prevents a caller from smuggling a
    whole payload (with credentials inside) into the trail.
    """
    if not details:
        return None
    cleaned = {
        str(key)[:64]: _clean_value(value)
        for key, value in list(details.items())[:_MAX_ITEMS]
        if not _SENSITIVE_KEY.search(str(key)) and not isinstance(value, dict)
    }
    return cleaned or None


def record(
    db: Session,
    action: str,
    *,
    resource_type: str,
    resource_id: int | str | None = None,
    actor: User | None = None,
    details: dict[str, Any] | None = None,
    context: AuditContext | None = None,
) -> None:
    """Append one audit row. Never raises (see module docstring)."""
    context = context or AuditContext()
    try:
        audit_crud.create_entry(
            db,
            action=action,
            resource_type=resource_type,
            resource_id=None if resource_id is None else str(resource_id)[:64],
            actor_user_id=actor.id if actor is not None else None,
            actor_email=actor.email if actor is not None else None,
            details=sanitize_details(details),
            ip_address=(context.ip_address or "")[:45] or None,
            user_agent=(context.user_agent or "")[:255] or None,
            request_id=(context.request_id or "")[:64] or None,
        )
    except Exception:  # noqa: BLE001 -- auditing must never break the request
        logger.exception("Could not write audit log entry: action=%s", action)
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass


def changed_fields(payload: Any) -> list[str]:
    """Names of the fields a Pydantic update payload actually set.

    Audit rows record *which* fields changed, never their values, so notes,
    descriptions and other free text written by HR never land in the trail.
    """
    try:
        return sorted(payload.model_dump(exclude_unset=True).keys())
    except AttributeError:
        return []
