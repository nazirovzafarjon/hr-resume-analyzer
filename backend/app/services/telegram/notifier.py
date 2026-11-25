"""Telegram notifications about applications.

* Candidates hear about their applications' status (bot phase 2).
* HR users hear about new applications to their own jobs (bot phase 3).

Two halves:

* **Queueing** (``queue_status_change``, ``queue_new_application``) runs inside
  the database transaction that creates or changes an application and records
  a ``send_telegram`` outbox event, so the notification exists exactly when
  that change commits.
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
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from app.bot.texts import STATUS_EMOJI, status_label, t
from app.core.config import settings
from app.models.application import Application, ApplicationStatus
from app.models.outbox import OutboxEvent
from app.models.interview import Interview, InterviewStatus
from app.models.telegram_link import (
    TelegramAccountKind,
    TelegramInterviewReminder,
    TelegramLink,
    TelegramReminderWindow,
)
from app.schemas.candidate import CandidateStatus

logger = logging.getLogger(__name__)

EVENT_TYPE = "send_telegram"
#: Candidate: one of their applications changed status (or was received).
APPLICATION_STATUS = "application_status"
#: HR: a new application arrived for one of their jobs (phase 3).
NEW_APPLICATION = "new_application"
#: Candidate and HR: an interview is coming up (phase 5).
INTERVIEW_REMINDER = "interview_reminder"

#: How often ``scan_interview_reminders`` runs (Celery beat) and the windows.
REMINDER_SCAN_SECONDS = 300
_REMINDER_WINDOWS = {
    TelegramReminderWindow.DAY: timedelta(hours=24),
    TelegramReminderWindow.HOUR: timedelta(hours=1),
}

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


def _hr_link(db: Session, user_id: int) -> TelegramLink | None:
    return (
        db.query(TelegramLink)
        .filter(TelegramLink.kind == TelegramAccountKind.HR, TelegramLink.user_id == user_id)
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
    if link is None or not link.is_active or not link.notify_status:
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


def queue_new_application(db: Session, application: Application) -> OutboxEvent | None:
    """Record the "new application" notification for the job's HR owner.

    Only the owner of the job is told (never other HR users); nothing is
    queued when the bot is off or the owner has no active HR link. The caller
    commits.
    """
    if not settings.telegram_configured:
        return None
    job = application.job
    if job is None:
        return None
    link = _hr_link(db, job.owner_id)
    if link is None or not link.is_active or not link.notify_new_applications:
        return None

    from app.services.outbox import record_outbox_event  # avoid an import cycle

    return record_outbox_event(
        db,
        EVENT_TYPE,
        {"notification": NEW_APPLICATION, "application_id": application.id},
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


def _site_url(path: str) -> str | None:
    """``FRONTEND_BASE_URL`` + ``path``, or ``None`` when Telegram would refuse it."""
    base = settings.FRONTEND_BASE_URL.rstrip("/")
    parsed = urlparse(base)
    if parsed.scheme not in ("http", "https") or (parsed.hostname or "") in _LOCAL_HOSTS:
        return None
    return f"{base}{path}"


def portal_url(application_id: int) -> str | None:
    """Candidate Portal page of the application, if Telegram can open it."""
    return _site_url(f"/candidate/applications/{application_id}")


def crm_url(application_id: int) -> str | None:
    """HR CRM page of the application, if Telegram can open it."""
    return _site_url(f"/applications/{application_id}")


def application_buttons(lang: str, application_id: int, page: int = 0) -> list[list[dict[str, str]]]:
    """"Details" (opens the card in the bot) and, when reachable, the website."""
    rows = [[{"text": t(lang, "btn_details"), "callback_data": f"app:{application_id}:{page}"}]]
    url = portal_url(application_id)
    if url:
        rows.append([{"text": t(lang, "btn_open_site"), "url": url}])
    return rows


def hr_application_buttons(lang: str, application_id: int, page: int = 0) -> list[list[dict[str, str]]]:
    """HR card in the bot and, when reachable, the application in the CRM."""
    rows = [[{"text": t(lang, "btn_details"), "callback_data": f"hr:app:{application_id}:{page}"}]]
    url = crm_url(application_id)
    if url:
        rows.append([{"text": t(lang, "btn_open_crm"), "url": url}])
    return rows


def build_message(db: Session, payload: dict) -> OutgoingMessage | None:
    """Render a queued notification, or ``None`` when it should be dropped."""
    kind = payload.get("notification")
    if kind == APPLICATION_STATUS:
        return _build_status_message(db, payload)
    if kind == NEW_APPLICATION:
        return _build_new_application_message(db, payload)
    if kind == INTERVIEW_REMINDER:
        return _build_reminder_message(db, payload)
    logger.warning("Unknown Telegram notification type: %s", kind)
    return None


def _build_new_application_message(db: Session, payload: dict) -> OutgoingMessage | None:
    application = db.get(Application, payload.get("application_id"))
    if application is None or application.job is None:
        return None
    # Re-read at send time: the job may have changed hands or the HR unlinked.
    link = _hr_link(db, application.job.owner_id)
    if (
        link is None
        or not link.is_active
        or not link.notify_new_applications
        or not link_owner_active(db, link)
    ):
        return None
    lang = link.language
    text = t(
        lang,
        "new_application",
        position=html.escape(application.job.position),
        company=html.escape(application.job.company_name),
        name=html.escape(application.name or "—"),
        date=format_date(application.submitted_at, with_time=True),
    )
    return OutgoingMessage(
        link_id=link.id,
        chat_id=link.chat_id,
        text=text,
        buttons=hr_application_buttons(lang, application.id),
    )


def _build_status_message(db: Session, payload: dict) -> OutgoingMessage | None:
    application = db.get(Application, payload.get("application_id"))
    if application is None or application.candidate_account_id is None:
        return None
    link = _candidate_link(db, application.candidate_account_id)
    if link is None or not link.is_active or not link.notify_status:
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


# ---------------------------------------------------------------------------
# Interview reminders (phase 5)
# ---------------------------------------------------------------------------

AUDIENCE_CANDIDATE = "candidate"
AUDIENCE_HR = "hr"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _reminder_window(time_left: timedelta) -> TelegramReminderWindow:
    """The window an interview ``time_left`` away falls into (the closest one)."""
    if time_left <= _REMINDER_WINDOWS[TelegramReminderWindow.HOUR]:
        return TelegramReminderWindow.HOUR
    return TelegramReminderWindow.DAY


def _reminder_recipients(db: Session, interview: Interview) -> list[str]:
    """Audiences that want this reminder: linked, active, switch on."""
    audiences = []
    application = interview.candidate
    if application is not None and application.candidate_account_id is not None:
        link = _candidate_link(db, application.candidate_account_id)
        if link is not None and link.is_active and link.notify_reminders:
            audiences.append(AUDIENCE_CANDIDATE)
    link = _hr_link(db, interview.hr_id)
    if link is not None and link.is_active and link.notify_reminders:
        audiences.append(AUDIENCE_HR)
    return audiences


def scan_interview_reminders(db: Session, now: datetime | None = None) -> list[OutboxEvent]:
    """Queue the reminders that are due and return their committed events.

    Runs every ``REMINDER_SCAN_SECONDS`` (Celery beat). An upcoming interview
    at most 24 hours away gets the "24h" reminder; at most one hour away, the
    "1h" one. Each (interview, window, time) is handled once: the
    ``TelegramInterviewReminder`` row commits together with the events.
    """
    if not settings.telegram_configured:
        return []
    now = now or _utcnow()
    horizon = now + _REMINDER_WINDOWS[TelegramReminderWindow.DAY]
    interviews = (
        db.query(Interview)
        .filter(
            Interview.status == InterviewStatus.UPCOMING,
            Interview.scheduled_at > now,
            Interview.scheduled_at <= horizon,
        )
        .order_by(Interview.scheduled_at)
        .all()
    )

    from app.services.outbox import record_outbox_event  # avoid an import cycle

    events: list[OutboxEvent] = []
    for interview in interviews:
        scheduled_at = _as_utc(interview.scheduled_at)
        window = _reminder_window(scheduled_at - now)
        already = (
            db.query(TelegramInterviewReminder.id)
            .filter(
                TelegramInterviewReminder.interview_id == interview.id,
                TelegramInterviewReminder.reminder_window == window.value,
                TelegramInterviewReminder.scheduled_at == scheduled_at,
            )
            .first()
        )
        if already:
            continue
        db.add(
            TelegramInterviewReminder(
                interview_id=interview.id, reminder_window=window.value, scheduled_at=scheduled_at
            )
        )
        for audience in _reminder_recipients(db, interview):
            events.append(
                record_outbox_event(
                    db,
                    EVENT_TYPE,
                    {
                        "notification": INTERVIEW_REMINDER,
                        "interview_id": interview.id,
                        "window": window.value,
                        "audience": audience,
                        "scheduled_at": scheduled_at.isoformat(),
                    },
                )
            )
    db.commit()
    return events


def _meeting_line(link: str | None) -> str | None:
    if not link:
        return None
    parsed = urlparse(link.strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    return f"🔗 {html.escape(link.strip())}"


def _build_reminder_message(db: Session, payload: dict) -> OutgoingMessage | None:
    interview = db.get(Interview, payload.get("interview_id"))
    if interview is None or interview.status != InterviewStatus.UPCOMING:
        return None
    scheduled_at = _as_utc(interview.scheduled_at)
    # Moved or already over since it was queued: this reminder is stale.
    if scheduled_at.isoformat() != payload.get("scheduled_at") or scheduled_at <= _utcnow():
        return None
    application = interview.candidate
    if application is None or application.job is None:
        return None

    audience = payload.get("audience")
    if audience == AUDIENCE_CANDIDATE:
        if application.candidate_account_id is None:
            return None
        link = _candidate_link(db, application.candidate_account_id)
        buttons = application_buttons
    elif audience == AUDIENCE_HR:
        link = _hr_link(db, interview.hr_id)
        buttons = hr_application_buttons
    else:
        return None
    if link is None or not link.is_active or not link.notify_reminders or not link_owner_active(db, link):
        return None

    lang = link.language
    lines = [
        t(lang, "reminder_title"),
        "",
    ]
    if audience == AUDIENCE_HR:
        lines.append(f"👤 {html.escape(application.name or '—')}")
    lines += [
        f"<b>{html.escape(application.job.position)}</b> — {html.escape(application.job.company_name)}",
        f"🗓 <b>{format_date(scheduled_at, with_time=True)}</b>",
        t(lang, "reminder_hour" if payload.get("window") == TelegramReminderWindow.HOUR.value else "reminder_day"),
    ]
    meeting = _meeting_line(interview.meeting_link)
    if meeting:
        lines.append(meeting)
    return OutgoingMessage(
        link_id=link.id,
        chat_id=link.chat_id,
        text="\n".join(lines),
        buttons=buttons(lang, application.id),
    )
