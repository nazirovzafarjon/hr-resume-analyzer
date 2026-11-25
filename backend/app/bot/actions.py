"""What each bot command does, as plain synchronous functions.

The aiogram handlers only translate a Telegram message into a call here and
send the returned text back, so the behaviour is tested without Telegram.
Every function opens its own short database session (the handlers run them in
a worker thread so the event loop never blocks on PostgreSQL).
"""

from __future__ import annotations

import html
import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import contains_eager

from app.bot.texts import (
    STATUS_EMOJI,
    TIMELINE_STATE_EMOJI,
    hr_status_label,
    status_label,
    t,
    timeline_label,
)
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.application import AnalysisStatus, Application, ApplicationStatus
from app.models.job import Job
from app.models.telegram_link import TelegramAccountKind
from app.services import candidate_portal
from app.services.telegram import linking, notifier
from app.services.telegram.linking import TelegramProfile

logger = logging.getLogger(__name__)


def _site_line() -> str:
    return html.escape(settings.FRONTEND_BASE_URL)


def start(profile: TelegramProfile, payload: str | None) -> str:
    """``/start`` with a link token links the account; without one it greets."""
    lang = profile.language_code
    with SessionLocal() as db:
        if not payload:
            linking.touch(db, profile.telegram_user_id, profile.chat_id)
            if linking.links_for_telegram_user(db, profile.telegram_user_id):
                return status(profile)
            return t(lang, "welcome", site=_site_line())
        try:
            link = linking.consume_link_token(db, payload.strip(), profile)
        except linking.LinkTokenError as exc:
            return t(lang, f"token_{exc.code}")
        owner = linking.owner_of(db, link)
        key = "linked_hr" if link.kind == TelegramAccountKind.HR else "linked_candidate"
        return t(lang, key, email=html.escape(owner.email if owner else ""))


def status(profile: TelegramProfile) -> str:
    """``/status``: which accounts this Telegram user is linked to."""
    lang = profile.language_code
    with SessionLocal() as db:
        links = linking.links_for_telegram_user(db, profile.telegram_user_id)
        if not links:
            return t(lang, "status_none")
        lines = [t(lang, "status_header")]
        for link in links:
            owner = linking.owner_of(db, link)
            key = "status_hr" if link.kind == TelegramAccountKind.HR else "status_candidate"
            lines.append(t(lang, key, email=html.escape(owner.email if owner else "")))
        return "\n".join(lines)


def unlink(profile: TelegramProfile) -> str:
    """``/unlink``: drop every link of this Telegram user."""
    with SessionLocal() as db:
        removed = linking.unlink_telegram_user(db, profile.telegram_user_id)
    return t(profile.language_code, "unlinked" if removed else "unlink_none")


def help_text(profile: TelegramProfile) -> str:
    return t(profile.language_code, "help")


# ---------------------------------------------------------------------------
# Candidate: /applications (phase 2)
# ---------------------------------------------------------------------------

PAGE_SIZE = 5

Buttons = list[list[dict[str, str]]]


@dataclass(frozen=True)
class Reply:
    """A message to send or edit: HTML text plus inline keyboard rows."""

    text: str
    buttons: Buttons = field(default_factory=list)


def _candidate_for(db, profile: TelegramProfile):
    """The active candidate account linked to this Telegram user, or ``None``."""
    for link in linking.links_for_telegram_user(db, profile.telegram_user_id):
        if link.kind == TelegramAccountKind.CANDIDATE:
            return linking.owner_of(db, link)
    return None


def applications_page(profile: TelegramProfile, page: int = 0) -> Reply:
    """Paginated list of the candidate's applications with their status."""
    lang = profile.language_code
    with SessionLocal() as db:
        candidate = _candidate_for(db, profile)
        if candidate is None:
            return Reply(t(lang, "apps_not_candidate"))
        summaries = candidate_portal.list_applications(db, candidate)
    if not summaries:
        return Reply(t(lang, "apps_empty"))

    pages = (len(summaries) + PAGE_SIZE - 1) // PAGE_SIZE
    page = min(max(page, 0), pages - 1)
    chunk = summaries[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]

    lines = [t(lang, "apps_header", total=str(len(summaries)), page=str(page + 1), pages=str(pages)), ""]
    buttons: Buttons = []
    for number, summary in enumerate(chunk, start=page * PAGE_SIZE + 1):
        status = summary.status.value
        lines.append(
            f"{number}. <b>{html.escape(summary.position)}</b> — {html.escape(summary.company_name)}\n"
            f"    {STATUS_EMOJI[status]} {status_label(lang, status)}"
        )
        buttons.append(
            [{"text": f"{number}. {summary.position[:48]}", "callback_data": f"app:{summary.id}:{page}"}]
        )
    nav = []
    if page > 0:
        nav.append({"text": t(lang, "btn_prev"), "callback_data": f"apps:{page - 1}"})
    if page < pages - 1:
        nav.append({"text": t(lang, "btn_next"), "callback_data": f"apps:{page + 1}"})
    if nav:
        buttons.append(nav)
    return Reply("\n".join(lines), buttons)


def application_detail(profile: TelegramProfile, application_id: int, page: int = 0) -> Reply:
    """One application: status, next interview and the progress timeline."""
    lang = profile.language_code
    back = [{"text": t(lang, "btn_back"), "callback_data": f"apps:{page}"}]
    with SessionLocal() as db:
        candidate = _candidate_for(db, profile)
        if candidate is None:
            return Reply(t(lang, "apps_not_candidate"))
        # Scoped to this candidate: another person's application id finds nothing.
        application = candidate_portal.get_application(db, candidate, application_id)
        if application is None:
            return Reply(t(lang, "app_not_found"), [back])
        summary = candidate_portal.application_summary(application)
        steps = candidate_portal.timeline(application)

    status = summary.status.value
    lines = [
        f"<b>{html.escape(summary.position)}</b>",
        html.escape(summary.company_name),
        "",
        f"{STATUS_EMOJI[status]} <b>{status_label(lang, status)}</b>",
        t(lang, "app_submitted", date=notifier.format_date(summary.submitted_at)),
    ]
    if summary.next_interview_at:
        lines.append(
            t(lang, "app_next_interview", date=notifier.format_date(summary.next_interview_at, with_time=True))
        )
    lines += ["", t(lang, "app_timeline")]
    for step in steps:
        key = f"decision_{step.outcome}" if step.key == "decision" and step.outcome else step.key
        label = timeline_label(lang, key)
        date = f" — {notifier.format_date(step.date)}" if step.date else ""
        lines.append(f"{TIMELINE_STATE_EMOJI[step.state.value]} {label}{date}")

    buttons: Buttons = []
    url = notifier.portal_url(summary.id)
    if url:
        buttons.append([{"text": t(lang, "btn_open_site"), "url": url}])
    buttons.append(back)
    return Reply("\n".join(lines), buttons)


# ---------------------------------------------------------------------------
# HR: /new (phase 3)
# ---------------------------------------------------------------------------


def _hr_for(db, profile: TelegramProfile):
    """The active, verified HR user linked to this Telegram user, or ``None``.

    The bot is the HR workspace: an HR user (admins included) only ever sees
    applications to the jobs they own here, never the organisation-wide scope.
    """
    for link in linking.links_for_telegram_user(db, profile.telegram_user_id):
        if link.kind == TelegramAccountKind.HR:
            user = linking.owner_of(db, link)
            if user is not None and user.is_active and user.is_email_verified:
                return user
    return None


def _owned_new_applications(db, owner_id: int):
    return (
        db.query(Application)
        .join(Application.job)
        .filter(Job.owner_id == owner_id, Application.application_status == ApplicationStatus.NEW)
        .options(contains_eager(Application.job))
    )


def hr_new_page(profile: TelegramProfile, page: int = 0) -> Reply:
    """Paginated list of unreviewed (``new``) applications to the HR's jobs."""
    lang = profile.language_code
    with SessionLocal() as db:
        user = _hr_for(db, profile)
        if user is None:
            return Reply(t(lang, "hr_not_hr"))
        query = _owned_new_applications(db, user.id)
        total = query.count()
        if total == 0:
            return Reply(t(lang, "hr_new_empty"))
        pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
        page = min(max(page, 0), pages - 1)
        chunk = (
            query.order_by(Application.submitted_at.desc(), Application.id.desc())
            .offset(page * PAGE_SIZE)
            .limit(PAGE_SIZE)
            .all()
        )
        rows = [
            (a.id, a.name or "—", a.job.position, a.job.company_name, a.submitted_at)
            for a in chunk
        ]

    lines = [t(lang, "hr_new_header", total=str(total), page=str(page + 1), pages=str(pages)), ""]
    buttons: Buttons = []
    for number, (app_id, name, position, company, submitted) in enumerate(rows, start=page * PAGE_SIZE + 1):
        lines.append(
            f"{number}. <b>{html.escape(name)}</b>\n"
            f"    {html.escape(position)} — {html.escape(company)} · {notifier.format_date(submitted)}"
        )
        buttons.append([{"text": f"{number}. {name[:48]}", "callback_data": f"hr:app:{app_id}:{page}"}])
    nav = []
    if page > 0:
        nav.append({"text": t(lang, "btn_prev"), "callback_data": f"hr:new:{page - 1}"})
    if page < pages - 1:
        nav.append({"text": t(lang, "btn_next"), "callback_data": f"hr:new:{page + 1}"})
    if nav:
        buttons.append(nav)
    return Reply("\n".join(lines), buttons)


def _ai_line(lang: str, application: Application) -> str:
    state = application.analysis_status
    if state == AnalysisStatus.COMPLETED:
        return t(lang, "hr_ai_score", score=str(round(application.ai_score or 0)))
    if state == AnalysisStatus.ANALYZING:
        return t(lang, "hr_ai_running")
    if state == AnalysisStatus.FAILED:
        return t(lang, "hr_ai_failed")
    return t(lang, "hr_ai_none")


def hr_application_detail(profile: TelegramProfile, application_id: int, page: int = 0) -> Reply:
    """One application to the HR's own job: applicant, status and AI match."""
    lang = profile.language_code
    back = [{"text": t(lang, "btn_back"), "callback_data": f"hr:new:{page}"}]
    with SessionLocal() as db:
        user = _hr_for(db, profile)
        if user is None:
            return Reply(t(lang, "hr_not_hr"))
        # Scoped to the HR's own jobs: another owner's application id finds nothing.
        application = (
            db.query(Application)
            .join(Application.job)
            .filter(Application.id == application_id, Job.owner_id == user.id)
            .options(contains_eager(Application.job))
            .one_or_none()
        )
        if application is None:
            return Reply(t(lang, "app_not_found"), [back])
        status = ApplicationStatus(application.application_status or ApplicationStatus.NEW).value
        lines = [
            f"👤 <b>{html.escape(application.name or '—')}</b>",
            f"✉️ {html.escape(application.email or '—')}",
            "",
            f"<b>{html.escape(application.job.position)}</b> — {html.escape(application.job.company_name)}",
            t(lang, "app_submitted", date=notifier.format_date(application.submitted_at, with_time=True)),
            t(lang, "hr_app_status", status=hr_status_label(lang, status)),
            _ai_line(lang, application),
        ]

    buttons: Buttons = []
    url = notifier.crm_url(application_id)
    if url:
        buttons.append([{"text": t(lang, "btn_open_crm"), "url": url}])
    buttons.append(back)
    return Reply("\n".join(lines), buttons)
