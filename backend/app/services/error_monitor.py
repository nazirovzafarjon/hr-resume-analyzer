"""Persist 5xx errors for the admin "System Errors" page.

Called from the application's exception handlers (see ``app.main``). Each
error is written in its *own* short-lived session: the request's session may
be the thing that just failed, and a broken transaction there must not stop
the error from being recorded (nor may recording roll back request work).

What is stored is intentionally small (see ``models.system_error``). The
message is scrubbed of anything that looks like a credential, because
exception text can quote connection strings or headers.
"""

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import TOKEN_PURPOSE_ACCESS, decode_token_for_purposes
from app.crud import system_error as system_error_crud
from app.models.user import User

logger = logging.getLogger(__name__)

_MAX_MESSAGE = 500

# Credential-looking fragments replaced before storage.
_SCRUB_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # user:password@host in database / broker URLs
    (re.compile(r"(\w+://[^:/\s]+):[^@\s]+@"), r"\1:***@"),
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"), "Bearer ***"),
    (re.compile(r"(?i)((?:api[_-]?key|token|secret|password|authorization)\s*[=:]\s*)\S+"), r"\1***"),
    # Long opaque strings (JWTs, provider keys such as sk-..., gsk_...)
    (re.compile(r"\b(?:sk|gsk|pk|rk)[-_][A-Za-z0-9\-_]{12,}\b"), "***"),
    (re.compile(r"\beyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\b"), "***"),
)


def scrub(message: str) -> str:
    """Remove credential-looking content and cap the length."""
    for pattern, replacement in _SCRUB_PATTERNS:
        message = pattern.sub(replacement, message)
    return message[:_MAX_MESSAGE]


def user_id_from_authorization(header: str | None) -> int | None:
    """Best-effort user id from a bearer token, without touching the database.

    Only used to attribute an error to a user; an invalid or expired token
    simply yields ``None``. Never used for authorization.
    """
    if not header or not header.lower().startswith("bearer "):
        return None
    try:
        payload = decode_token_for_purposes(header[7:].strip(), (TOKEN_PURPOSE_ACCESS,))
        return int(payload["sub"])
    except (JWTError, KeyError, TypeError, ValueError):
        return None


def record_error(
    *,
    method: str,
    path: str,
    status_code: int,
    error_type: str,
    message: str = "",
    request_id: str | None = None,
    user_id: int | None = None,
) -> None:
    """Store one error row. Never raises: monitoring must not mask the error."""
    db = SessionLocal()
    try:
        system_error_crud.create_error(
            db,
            method=method[:10],
            path=path[:500],
            status_code=status_code,
            error_type=error_type[:120],
            message=scrub(message or ""),
            request_id=request_id[:64] if request_id else None,
            user_id=user_id,
        )
    except Exception:  # noqa: BLE001 -- e.g. the database itself is down
        logger.warning(
            "Could not persist system error (status=%s path=%s request_id=%s)",
            status_code,
            path,
            request_id,
            exc_info=True,
        )
        db.rollback()
    finally:
        db.close()


def list_errors(db: Session, *, page: int, limit: int, **filters: Any) -> dict[str, Any]:
    """One page of errors with the affected user's email, plus a summary."""
    rows, total = system_error_crud.list_errors(db, page=page, limit=limit, **filters)
    # One lookup for every user on the page instead of one per row.
    user_ids = {row.user_id for row in rows if row.user_id is not None}
    emails = (
        dict(db.execute(select(User.id, User.email).where(User.id.in_(user_ids))).all())
        if user_ids
        else {}
    )
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    return {
        "items": [
            {
                "id": row.id,
                "created_at": row.created_at,
                "request_id": row.request_id,
                "method": row.method,
                "path": row.path,
                "status_code": row.status_code,
                "error_type": row.error_type,
                "message": row.message,
                "user_id": row.user_id,
                "user_email": emails.get(row.user_id),
            }
            for row in rows
        ],
        "total": total,
        "page": page,
        "limit": limit,
        "summary": {
            "last_24h": system_error_crud.count_since(db, now - timedelta(hours=24)),
            "last_7d": system_error_crud.count_since(db, week_ago),
            "by_status_7d": [
                {"key": str(code), "count": count}
                for code, count in sorted(system_error_crud.status_code_counts(db, week_ago).items())
            ],
        },
    }
