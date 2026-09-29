"""Business logic for the public Contact Us form.

The endpoint needs no account, so the only abuse guard is a small in-process
per-client limit. Like ``app.core.token_registry`` it lives in the worker's
memory: a restart resets it and several uvicorn workers each keep their own
count. That is enough to stop a stuck button or a naive script without adding
Redis for one form; back it with a shared store if the API is scaled out.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque

from sqlalchemy.orm import Session

from app.crud import contact_message as contact_message_crud
from app.models.contact_message import ContactMessage
from app.schemas.contact_message import ContactMessageCreate

logger = logging.getLogger(__name__)

#: At most this many messages per client within ``RATE_LIMIT_WINDOW_SECONDS``.
RATE_LIMIT_MAX_MESSAGES = 5
RATE_LIMIT_WINDOW_SECONDS = 10 * 60

_lock = threading.Lock()
# client key -> monotonic timestamps of its recent submissions.
_recent: dict[str, deque[float]] = {}


class ContactRateLimitError(Exception):
    """Raised when a client sends too many messages in a short time."""

    message = "Too many messages. Please try again later."


def _check_rate_limit(client_key: str) -> None:
    """Record a submission for ``client_key`` or raise when over the limit."""
    now = time.monotonic()
    cutoff = now - RATE_LIMIT_WINDOW_SECONDS
    with _lock:
        # Drop idle clients so the map cannot grow without bound.
        for key in [key for key, stamps in _recent.items() if stamps[-1] < cutoff]:
            del _recent[key]

        stamps = _recent.setdefault(client_key, deque())
        while stamps and stamps[0] < cutoff:
            stamps.popleft()
        if len(stamps) >= RATE_LIMIT_MAX_MESSAGES:
            raise ContactRateLimitError()
        stamps.append(now)


def reset_rate_limit() -> None:
    """Forget every recorded submission (used by the test suite)."""
    with _lock:
        _recent.clear()


def submit_contact_message(
    db: Session, payload: ContactMessageCreate, client_key: str
) -> ContactMessage:
    """Rate-limit, then store a Contact Us message.

    Raises:
        ContactRateLimitError: When ``client_key`` exceeded the limit.
    """
    _check_rate_limit(client_key)
    contact_message = contact_message_crud.create_contact_message(db, payload)
    logger.info("Stored contact message id=%s", contact_message.id)
    return contact_message
