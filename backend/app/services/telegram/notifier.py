"""Candidate notifications about their applications (Telegram bot phase 2).

Two halves:

* **Queueing** (``queue_status_change``) runs inside the database transaction
  that changes an application's status and records a ``send_telegram`` outbox
  event, so the notification exists exactly when the status change commits.
* **Building** (``build_message``) runs later in the Celery task: it reloads
  the application and the link, and renders the text in the chat's language.

Only candidate-facing changes are announced. HR statuses are grouped the way
the Candidate Portal shows them, so e.g. ``reviewing -> shortlisted`` (both
"Under HR review" for the candidate) sends nothing, and internal terms never
leave the server.
"""

from __future__ import annotations

import html
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from app.bot.texts import STATUS_EMOJI, status_label, t
from app.core.config import settings
from app.models.application import Application, ApplicationStatus
from app.models.outbox import OutboxEvent
from app.models.telegram_link import TelegramAccountKind, TelegramLink
from app.schemas.candidate import CandidateStatus

logger = logging.getLogger(__name__)

EVENT_TYPE = "send_telegram"
APPLICATION_STATUS = "application_status"

#: HR pipeline status -> what the candidate sees (cf. candidate_portal.candidate_status).
_CANDIDATE_FACING: dict[ApplicationStatus, CandidateStatus] = {
    ApplicationStatus.NEW: CandidateStatus.SUBMITTED,
    ApplicationStatus.REVIEWING: CandidateStatus.HR_REVIEW,
    ApplicationStatus.SHORTLISTED: CandidateStatus.HR_REVIEW,
    ApplicationStatus.INTERVIEW: CandidateStatus.INTERVIEW_INVITED,
    ApplicationStatus.HIRED: CandidateStatus.ACCEPTED,
    ApplicationStatus.REJECTED: CandidateStatus.REJECTED,
    ApplicationStatus.WITHDRAWN: CandidateStatus.WITHDRAWN,
}

#: Hosts Telegram refuses in URL buttons; such links are left out.
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


def candidate_facing(status: ApplicationStatus | str | None) -> CandidateStatus:
    return _CANDIDATE_FACING[ApplicationStatus(status or ApplicationStatus.NEW)]


def _candidate_link(db: Session, candidate_account_id: int) -> TelegramLink | None:
    return (
        db.query(TelegramLink)
        .filter(
            TelegramLink.kind == TelegramAccountKind.CANDIDATE,
            TelegramLink.candidate_account_id == candidate_account_id,
        )
        .one_or_none()
    )


# ---------------------------------------------------------------------------
# Queueing (inside the status-change transaction)
# ---------------------------------------------------------------------------


def queue_status_change(
    db: Session,
    application: Application,
    previous_status: ApplicationStatus | None,
) -> OutboxEvent | None:
    """Record a notification when the candidate-facing status changed.

    ``previous_status`` is ``None`` for a newly created application, which
    produces the "application received" confirmation. Nothing is queued when
    the bot is off, the application has no candidate account, or that account
    has no active Telegram link. The caller commits.
    """
    if not settings.telegram_configured or application.candidate_account_id is None:
        return None
    current = candidate_facing(application.application_status)
    if previous_status is not None and candidate_facing(previous_status) == current:
        return None
    link = _candidate_link(db, application.candidate_account_id)
    if link is None or not link.is_active:
        return None

    from app.services.outbox import record_outbox_event  # avoid an import cycle

    return record_outbox_event(
        db,
        EVENT_TYPE,
        {
            "notification": APPLICATION_STATUS,
            "application_id": application.id,
            "status": current.value,
            "created": previous_status is None,
        },
    )


def publish(db: Session, event: OutboxEvent | None) -> None:
    """Hand a committed event to Celery now; never fails the caller.

    If publishing fails the event stays pending and the outbox recovery task
    retries it (see ``tasks.outbox``).
    """
    if event is None:
        return
    from app.services.outbox import publish_outbox_event  # avoid an import cycle

    try:
        publish_outbox_event(db, event)
    except Exception:  # noqa: BLE001 -- a notification must never break a status change
        logger.exception("Could not publish Telegram notification event id=%s", event.id)
        db.rollback()


# ---------------------------------------------------------------------------
# Building (inside the Celery task)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OutgoingMessage:
    link_id: int
    chat_id: int
    text: str
    buttons: list[list[dict[str, str]]] = field(default_factory=list)


def _timezone():
    try:
        return ZoneInfo(settings.TELEGRAM_TIMEZONE)
    except (ZoneInfoNotFoundError, ValueError):
        return timezone.utc


def format_date(value: datetime | None, *, with_time: bool = False) -> str:
    """Local date (``TELEGRAM_TIMEZONE``) as ``24.11.2026`` or ``24.11.2026 14:30``."""
    if value is None:
        return "—"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    local = value.astimezone(_timezone())
    return local.strftime("%d.%m.%Y %H:%M" if with_time else "%d.%m.%Y")


def portal_url(application_id: int) -> str | None:
    """Candidate Portal page of the application, if Telegram can open it."""
    base = settings.FRONTEND_BASE_URL.rstrip("/")
    parsed = urlparse(base)
    if parsed.scheme not in ("http", "https") or (parsed.hostname or "") in _LOCAL_HOSTS:
        return None
    return f"{base}/candidate/applications/{application_id}"


def application_buttons(lang: str, application_id: int, page: int = 0) -> list[list[dict[str, str]]]:
    """"Details" (opens the card in the bot) and, when reachable, the website."""
    rows = [[{"text": t(lang, "btn_details"), "callback_data": f"app:{application_id}:{page}"}]]
    url = portal_url(application_id)
    if url:
        rows.append([{"text": t(lang, "btn_open_site"), "url": url}])
    return rows


def build_message(db: Session, payload: dict) -> OutgoingMessage | None:
    """Render a queued notification, or ``None`` when it should be dropped."""
    if payload.get("notification") != APPLICATION_STATUS:
        logger.warning("Unknown Telegram notification type: %s", payload.get("notification"))
        return None
    application = db.get(Application, payload.get("application_id"))
    if application is None or application.candidate_account_id is None:
        return None
    link = _candidate_link(db, application.candidate_account_id)
    if link is None or not link.is_active:
        return None
    owner = link_owner_active(db, link)
    if not owner:
        return None

    lang = link.language
    status = CandidateStatus(payload["status"])
    params = {
        "position": html.escape(application.job.position),
        "company": html.escape(application.job.company_name),
    }
    if payload.get("created"):
        text = t(lang, "application_received", **params)
    else:
        text = t(
            lang,
            "status_changed",
            emoji=STATUS_EMOJI[status.value],
            status=status_label(lang, status.value),
            **params,
        )
    return OutgoingMessage(
        link_id=link.id,
        chat_id=link.chat_id,
        text=text,
        buttons=application_buttons(lang, application.id),
    )


def link_owner_active(db: Session, link: TelegramLink) -> bool:
    from app.services.telegram.linking import owner_of

    owner = owner_of(db, link)
    return owner is not None and owner.is_active


def mark_blocked(db: Session, link_id: int) -> None:
    """Telegram said the user blocked the bot: stop sending until they return."""
    db.query(TelegramLink).filter(TelegramLink.id == link_id).update(
        {TelegramLink.is_active: False}, synchronize_session=False
    )
    db.commit()
