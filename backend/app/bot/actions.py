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
from datetime import date, datetime, time, timedelta, timezone
from urllib.parse import urlparse

from sqlalchemy import func, or_
from sqlalchemy.orm import contains_eager

from app.bot.texts import (
    STATUS_EMOJI,
    TIMELINE_STATE_EMOJI,
    hr_action_label,
    hr_status_label,
    status_label,
    t,
    timeline_label,
    weekday_label,
)
from app.core.config import settings
from app.core.database import SessionLocal
from app.crud import application as application_crud
from app.crud import interview as interview_crud
from app.models.application import AnalysisStatus, Application, ApplicationStatus
from app.models.interview import Interview, InterviewStatus
from app.models.job import Job
from app.models.telegram_link import TelegramAccountKind
from app.schemas.application import ApplicationUpdate
from app.schemas.interview import InterviewCreate, InterviewUpdate
from app.services import audit, candidate_portal
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
    """A message to send or edit: HTML text plus inline keyboard rows.

    ``awaiting_input`` asks the handler to treat the user's next plain text
    message as the answer (the meeting link, phase 6; a search, phase 8).
    """

    text: str
    buttons: Buttons = field(default_factory=list)
    awaiting_input: bool = False
    #: ``(path, filename)`` of a file to send, with ``text`` as its caption (phase 8).
    document: tuple[str, str] | None = None


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
# HR: application lists -- /new (phase 3), filters, jobs and search (phase 8)
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


#: List filters, in button order (phase 8). ``all`` includes withdrawn ones.
HR_FILTERS = ("new", "reviewing", "shortlisted", "interview", "hired", "rejected", "all")
#: Shortest search text the bot accepts.
MIN_SEARCH = 2
#: Most applications one "analyse the new ones" tap sends to the AI.
BULK_ANALYSIS_LIMIT = 50


def _owned_applications(db, owner_id: int):
    return (
        db.query(Application)
        .join(Application.job)
        .filter(Job.owner_id == owner_id)
        .options(contains_eager(Application.job))
    )


def _filter_label(lang: str, key: str) -> str:
    return t(lang, "filter_all") if key == "all" else hr_status_label(lang, key)


def _analysable_count(db, owner_id: int, job_id: int | None) -> int:
    from app.services.ai import batch as auto_analyze

    return auto_analyze.get_available_new_count(db, owner_id, job_id=job_id)


def hr_list(
    profile: TelegramProfile,
    status_filter: str = "new",
    job_id: int = 0,
    page: int = 0,
    query: str | None = None,
) -> Reply:
    """HR applications, filtered by status and job, or found by a search.

    Only applications to the HR user's own jobs. ``job_id=0`` means every job;
    with ``query`` the status and job filters are ignored and the name or
    email is searched instead.
    """
    lang = profile.language_code
    if status_filter not in HR_FILTERS:
        status_filter = "new"
    query = (query or "").strip() or None
    with SessionLocal() as db:
        user = _hr_for(db, profile)
        if user is None:
            return Reply(t(lang, "hr_not_hr"))
        rows_query = _owned_applications(db, user.id)
        job = None
        if query:
            like = f"%{query.lower()}%"
            rows_query = rows_query.filter(
                or_(func.lower(Application.name).like(like), func.lower(Application.email).like(like))
            )
        else:
            if status_filter != "all":
                rows_query = rows_query.filter(Application.application_status == ApplicationStatus(status_filter))
            if job_id:
                job = db.query(Job).filter(Job.id == job_id, Job.owner_id == user.id).one_or_none()
                if job is None:
                    job_id = 0
                else:
                    rows_query = rows_query.filter(Application.job_id == job_id)
        total = rows_query.count()
        pages = max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1)
        page = min(max(page, 0), pages - 1)
        chunk = (
            rows_query.order_by(Application.submitted_at.desc(), Application.id.desc())
            .offset(page * PAGE_SIZE)
            .limit(PAGE_SIZE)
            .all()
        )
        rows = [
            (
                a.id,
                a.name or "—",
                a.job.position,
                a.job.company_name,
                a.submitted_at,
                _current_status(a),
                round(a.ai_score) if a.analysis_status == AnalysisStatus.COMPLETED and a.ai_score is not None else None,
            )
            for a in chunk
        ]
        analysable = 0
        if not query and status_filter == "new":
            analysable = _analysable_count(db, user.id, job_id or None)
        job_line = (
            t(lang, "hr_list_job", position=html.escape(job.position), company=html.escape(job.company_name))
            if job is not None
            else None
        )

    title = t(lang, "btn_search") if query else _filter_label(lang, status_filter)
    lines = [t(lang, "hr_list_header", title=title, total=str(total), page=str(page + 1), pages=str(pages))]
    if query:
        lines.append(t(lang, "hr_list_search", query=html.escape(query)))
    if job_line:
        lines.append(job_line)
    lines.append("")
    if not rows:
        lines.append(t(lang, "hr_list_empty"))

    buttons: Buttons = []
    for number, (app_id, name, position, company, submitted, status, score) in enumerate(rows, start=page * PAGE_SIZE + 1):
        extra = f" · 🤖 {score}%" if score is not None else ""
        # The status is only news when the list mixes statuses.
        shown_status = f" · {hr_status_label(lang, status)}" if query or status_filter == "all" else ""
        lines.append(
            f"{number}. <b>{html.escape(name)}</b>{extra}\n"
            f"    {html.escape(position)} — {html.escape(company)} · {notifier.format_date(submitted)}{shown_status}"
        )
        buttons.append([{"text": f"{number}. {name[:48]}", "callback_data": f"hr:app:{app_id}:{page}"}])

    nav = []
    here = "hr:sr:{}" if query else f"hr:ls:{status_filter}:{job_id}:{{}}"
    if page > 0:
        nav.append({"text": t(lang, "btn_prev"), "callback_data": here.format(page - 1)})
    if page < pages - 1:
        nav.append({"text": t(lang, "btn_next"), "callback_data": here.format(page + 1)})
    if nav:
        buttons.append(nav)

    if analysable:
        buttons.append(
            [
                {
                    "text": t(lang, "btn_analyze_all", count=str(min(analysable, BULK_ANALYSIS_LIMIT))),
                    "callback_data": f"hr:aiall:{job_id}",
                }
            ]
        )
    if not query:
        filters = [
            {
                "text": f"{'• ' if key == status_filter else ''}{_filter_label(lang, key)}",
                "callback_data": f"hr:ls:{key}:{job_id}:0",
            }
            for key in HR_FILTERS
        ]
        buttons += [filters[i : i + 4] for i in range(0, len(filters), 4)]
        buttons.append(
            [
                {"text": t(lang, "btn_pick_job"), "callback_data": f"hr:jobs:{status_filter}"},
                {"text": t(lang, "btn_search"), "callback_data": "hr:find"},
            ]
        )
    else:
        buttons.append([{"text": t(lang, "btn_back"), "callback_data": "hr:ls:all:0:0"}])
    return Reply("\n".join(lines), buttons)


def hr_new_page(profile: TelegramProfile, page: int = 0) -> Reply:
    """``/new``: the unreviewed applications to the HR's jobs."""
    return hr_list(profile, "new", 0, page)


def applications_entry(profile: TelegramProfile) -> Reply:
    """``/applications``: the HR list for HR users, the own list for candidates.

    A Telegram user linked to both gets the HR list with a way to their own.
    """
    with SessionLocal() as db:
        is_hr = _hr_for(db, profile) is not None
        is_candidate = _candidate_for(db, profile) is not None
    if not is_hr:
        return applications_page(profile, 0)
    reply = hr_list(profile, "all")
    if is_candidate:
        reply.buttons.append(
            [{"text": t(profile.language_code, "btn_my_candidate_apps"), "callback_data": "apps:0"}]
        )
    return reply


def hr_jobs_picker(profile: TelegramProfile, status_filter: str = "new") -> Reply:
    """The HR's own jobs, newest first, to narrow the list to one of them."""
    lang = profile.language_code
    if status_filter not in HR_FILTERS:
        status_filter = "new"
    with SessionLocal() as db:
        user = _hr_for(db, profile)
        if user is None:
            return Reply(t(lang, "hr_not_hr"))
        jobs = (
            db.query(Job.id, Job.position, Job.company_name, func.count(Application.id))
            .outerjoin(Application, Application.job_id == Job.id)
            .filter(Job.owner_id == user.id)
            .group_by(Job.id, Job.position, Job.company_name)
            .order_by(Job.id.desc())
            .limit(30)
            .all()
        )
    back = [{"text": t(lang, "btn_back"), "callback_data": f"hr:ls:{status_filter}:0:0"}]
    if not jobs:
        return Reply(t(lang, "hr_jobs_empty"), [back])
    buttons: Buttons = [
        [
            {
                "text": f"{position[:36]} — {company[:20]} ({count})",
                "callback_data": f"hr:ls:{status_filter}:{job_id}:0",
            }
        ]
        for job_id, position, company, count in jobs
    ]
    buttons.append([{"text": t(lang, "btn_all_jobs"), "callback_data": f"hr:ls:{status_filter}:0:0"}])
    return Reply(t(lang, "hr_jobs_header"), buttons)


def hr_search_prompt(profile: TelegramProfile) -> Reply:
    """Ask for the search text; the next text message is the answer."""
    lang = profile.language_code
    with SessionLocal() as db:
        if _hr_for(db, profile) is None:
            return Reply(t(lang, "hr_not_hr"))
    return Reply(t(lang, "hr_search_prompt"), awaiting_input=True)


def hr_search(profile: TelegramProfile, text: str, page: int = 0) -> Reply:
    """Applications whose applicant name or email contains ``text``."""
    query = " ".join((text or "").split())[:100]
    if len(query) < MIN_SEARCH:
        return Reply(t(profile.language_code, "hr_search_short"), awaiting_input=True)
    return hr_list(profile, page=page, query=query)


def _ai_line(lang: str, application: Application) -> str:
    state = application.analysis_status
    if state == AnalysisStatus.COMPLETED:
        return t(lang, "hr_ai_score", score=str(round(application.ai_score or 0)))
    if state == AnalysisStatus.ANALYZING:
        return t(lang, "hr_ai_running")
    if state == AnalysisStatus.FAILED:
        return t(lang, "hr_ai_failed")
    return t(lang, "hr_ai_none")


def _owned_application(db, user, application_id: int) -> Application | None:
    """The application if it belongs to one of the HR user's own jobs."""
    return (
        db.query(Application)
        .join(Application.job)
        .filter(Application.id == application_id, Job.owner_id == user.id)
        .options(contains_eager(Application.job))
        .one_or_none()
    )


def _current_status(application: Application) -> str:
    return ApplicationStatus(application.application_status or ApplicationStatus.NEW).value


def _hr_card(lang: str, application: Application, page: int, notice: str | None = None) -> Reply:
    """Applicant, status, AI match and the status buttons (phase 4)."""
    status = _current_status(application)
    lines = []
    if notice:
        lines += [notice, ""]
    lines += [
        f"👤 <b>{html.escape(application.name or '—')}</b>",
        f"✉️ {html.escape(application.email or '—')}",
        "",
        f"<b>{html.escape(application.job.position)}</b> — {html.escape(application.job.company_name)}",
        t(lang, "app_submitted", date=notifier.format_date(application.submitted_at, with_time=True)),
        t(lang, "hr_app_status", status=hr_status_label(lang, status)),
        _ai_line(lang, application),
    ]
    upcoming = _next_interview(application)
    if upcoming is not None:
        lines.append(t(lang, "app_next_interview", date=notifier.format_date(upcoming.scheduled_at, with_time=True)))

    buttons: Buttons = []
    if status not in _CLOSED_STATUSES:
        buttons.append(
            [{"text": t(lang, "btn_schedule"), "callback_data": f"hr:iv:{application.id}:{page}"}]
        )
    if upcoming is not None:
        # Manage the next interview (phase 7); cancelling stays possible on
        # closed applications too.
        row = [{"text": t(lang, "btn_iv_cancel"), "callback_data": f"hr:ivx:{upcoming.id}:{page}"}]
        if status not in _CLOSED_STATUSES:
            row.insert(0, {"text": t(lang, "btn_reschedule"), "callback_data": f"hr:rs:{upcoming.id}:{page}"})
        buttons.append(row)
    # Resume, form answers and the AI analysis (phase 8).
    buttons.append(
        [
            {"text": t(lang, "btn_resume"), "callback_data": f"hr:cv:{application.id}:{page}"},
            {"text": t(lang, "btn_form"), "callback_data": f"hr:fa:{application.id}:{page}"},
        ]
    )
    state = application.analysis_status
    if state == AnalysisStatus.COMPLETED:
        buttons.append(
            [
                {"text": t(lang, "btn_ai_summary"), "callback_data": f"hr:aix:{application.id}:{page}"},
                {"text": t(lang, "btn_ai_rerun"), "callback_data": f"hr:air:{application.id}:{page}"},
            ]
        )
    elif state != AnalysisStatus.ANALYZING:
        buttons.append([{"text": t(lang, "btn_ai_start"), "callback_data": f"hr:ai:{application.id}:{page}"}])
    # A withdrawn application is the candidate's decision: HR cannot move it.
    if status != ApplicationStatus.WITHDRAWN.value:
        targets = [target for target in HR_TARGETS if target.value != status]
        actions_row = [
            {
                "text": hr_action_label(lang, target.value),
                "callback_data": f"hr:set:{application.id}:{target.value}:{page}",
            }
            for target in targets
        ]
        buttons += [actions_row[i : i + 2] for i in range(0, len(actions_row), 2)]
    url = notifier.crm_url(application.id)
    if url:
        buttons.append([{"text": t(lang, "btn_open_crm"), "url": url}])
    buttons.append(_back_to_list(lang, page))
    return Reply("\n".join(lines), buttons)


def hr_application_detail(profile: TelegramProfile, application_id: int, page: int = 0) -> Reply:
    """One application to the HR's own job: applicant, status and AI match."""
    lang = profile.language_code
    with SessionLocal() as db:
        user = _hr_for(db, profile)
        if user is None:
            return Reply(t(lang, "hr_not_hr"))
        # Scoped to the HR's own jobs: another owner's application id finds nothing.
        application = _owned_application(db, user, application_id)
        if application is None:
            return Reply(t(lang, "app_not_found"), [_back_to_list(lang, page)])
        return _hr_card(lang, application, page)


def _back_to_list(lang: str, page: int) -> list[dict[str, str]]:
    """Back to the list the card was opened from (the handler remembers it)."""
    return [{"text": t(lang, "btn_back"), "callback_data": f"hr:back:{page}"}]


def _back_to_card(lang: str, application_id: int, page: int) -> list[dict[str, str]]:
    return [{"text": t(lang, "btn_to_card"), "callback_data": f"hr:app:{application_id}:{page}"}]


def _load_owned(db, profile: TelegramProfile, application_id: int, page: int):
    """``(user, application, None)`` or ``(None, None, error reply)``."""
    lang = profile.language_code
    user = _hr_for(db, profile)
    if user is None:
        return None, None, Reply(t(lang, "hr_not_hr"))
    application = _owned_application(db, user, application_id)
    if application is None:
        return None, None, Reply(t(lang, "app_not_found"), [_back_to_list(lang, page)])
    return user, application, None


# ---------------------------------------------------------------------------
# HR: resume, form answers and AI analysis (phase 8)
# ---------------------------------------------------------------------------


def hr_resume(profile: TelegramProfile, application_id: int, page: int = 0) -> Reply:
    """The CV as a document (``Reply.document``), or why there is none."""
    from app.services import resume_file

    lang = profile.language_code
    with SessionLocal() as db:
        _, application, error = _load_owned(db, profile, application_id, page)
        if error is not None:
            return error
        try:
            resume = resume_file.get_resume_file(application)
        except resume_file.ResumeUnavailableError:
            return Reply(t(lang, "resume_missing"))
        caption = t(
            lang,
            "resume_caption",
            name=html.escape(application.name or "—"),
            position=html.escape(application.job.position),
        )
    return Reply(caption, document=(str(resume.path), resume.filename))


#: Longest piece of one answer or analysis item shown in a message.
_ITEM_LIMIT = 300
#: Stay well below Telegram's 4096-character message limit.
_MESSAGE_LIMIT = 3800


def _clip(text: str, limit: int = _ITEM_LIMIT) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _fit(lines: list[str]) -> str:
    text = "\n".join(lines)
    return text if len(text) <= _MESSAGE_LIMIT else text[: _MESSAGE_LIMIT - 1] + "…"


def hr_form_answers(profile: TelegramProfile, application_id: int, page: int = 0) -> Reply:
    """Every answer the applicant submitted through the job's form."""
    lang = profile.language_code
    with SessionLocal() as db:
        _, application, error = _load_owned(db, profile, application_id, page)
        if error is not None:
            return error
        response = application.application_response
        answers = (response.responses if response is not None else None) or []
        lines = [
            t(
                lang,
                "form_header",
                name=html.escape(application.name or "—"),
                position=html.escape(application.job.position),
            ),
            "",
        ]
        shown = 0
        for answer in answers:
            if not isinstance(answer, dict) or answer.get("type") == "file":
                continue
            label = str(answer.get("label") or answer.get("key") or "").strip()
            if not label:
                continue
            value = answer.get("value")
            if isinstance(value, list):
                value = ", ".join(str(item) for item in value)
            elif isinstance(value, bool):
                value = "✓" if value else "✗"
            rendered = _clip(value) if value not in (None, "") else "—"
            lines.append(f"<b>{html.escape(_clip(label, 120))}</b>\n{html.escape(rendered)}")
            shown += 1
        if not shown:
            lines.append(t(lang, "form_empty"))
    return Reply(_fit(lines), [_back_to_card(lang, application_id, page)])


def hr_analysis_summary(profile: TelegramProfile, application_id: int, page: int = 0) -> Reply:
    """The stored AI analysis: match, recommendation, summary, strengths, gaps, risks.

    Reads PostgreSQL only; it never calls the AI provider.
    """
    from app.services import application_analysis

    lang = profile.language_code
    with SessionLocal() as db:
        _, application, error = _load_owned(db, profile, application_id, page)
        if error is not None:
            return error
        analysis = application_analysis.stored_analysis(application)
        heading = t(
            lang,
            "ai_summary_title",
            name=html.escape(application.name or "—"),
            position=html.escape(application.job.position),
        )
        completed = application.analysis_status == AnalysisStatus.COMPLETED
    back = _back_to_card(lang, application_id, page)
    if analysis is None or not completed:
        return Reply(f"{heading}\n\n{t(lang, 'ai_none')}", [back])

    lines = [heading, "", t(lang, "hr_ai_score", score=str(round(analysis.match_percentage)))]
    if analysis.ai_recommendation:
        lines.append(t(lang, "ai_recommendation", value=t(lang, f"ai_rec_{analysis.ai_recommendation}")))
    if analysis.summary:
        lines += ["", html.escape(_clip(analysis.summary, 900))]
    sections = (
        ("ai_sec_strengths", analysis.strengths or analysis.matched_requirements, 5),
        ("ai_sec_gaps", analysis.missing_requirements or analysis.weaknesses, 5),
        ("ai_sec_risks", analysis.risks, 3),
    )
    for key, items, limit in sections:
        if items:
            lines += ["", t(lang, key)] + [f"• {html.escape(_clip(item))}" for item in items[:limit]]
    if not analysis.resume_text_available:
        lines += ["", t(lang, "ai_no_resume_text")]
    buttons: Buttons = [
        [{"text": t(lang, "btn_ai_rerun"), "callback_data": f"hr:air:{application_id}:{page}"}],
        back,
    ]
    return Reply(_fit(lines), buttons)


def hr_start_analysis(
    profile: TelegramProfile, application_id: int, page: int = 0, *, force: bool = False
) -> Reply:
    """Queue an AI analysis exactly like ``POST /applications/{id}/analyze``.

    The run goes through the outbox to the AI worker; the HR user gets a
    message when it has finished. The card comes back with the outcome.
    """
    from app.services import application_analysis
    from app.services.ai import provider as ai_provider
    from app.services.ai.job_analyzer import AIServiceError

    lang = profile.language_code
    with SessionLocal() as db:
        user, application, error = _load_owned(db, profile, application_id, page)
        if error is not None:
            return error
        try:
            started = application_analysis.start_analysis(db, application, actor_id=user.id, force=force)
            notice = t(lang, "ai_started" if started else "ai_already")
            if started:
                logger.info(
                    "AI analysis requested from Telegram: application_id=%s user_id=%s force=%s",
                    application_id,
                    user.id,
                    force,
                )
        except application_analysis.AnalysisInProgressError:
            notice = t(lang, "ai_running")
        except ai_provider.AIConfigurationRequiredError:
            notice = t(lang, "ai_no_provider")
        except ai_provider.AIDailyLimitError:
            notice = t(lang, "ai_daily_limit", limit=str(ai_provider.platform_cv_limit() or 0))
        except AIServiceError:
            notice = t(lang, "ai_key_failed")
        db.expire_all()
        application = _owned_application(db, user, application_id)
        return _hr_card(lang, application, page, notice=notice)


def hr_analyze_all(profile: TelegramProfile, job_id: int = 0, *, confirmed: bool = False) -> Reply:
    """Send the new, never analysed applications to the AI in one batch.

    Same as the CRM's Auto Analyze (oldest first, at most
    ``BULK_ANALYSIS_LIMIT``): asks first, then queues the batch. One summary
    message follows when the whole batch has finished.
    """
    from app.services import outbox as outbox_service
    from app.services.ai import batch as auto_analyze
    from app.services.ai import provider as ai_provider
    from app.services.ai.job_analyzer import AIServiceError

    lang = profile.language_code
    back = [{"text": t(lang, "btn_back"), "callback_data": f"hr:ls:new:{job_id}:0"}]
    with SessionLocal() as db:
        user = _hr_for(db, profile)
        if user is None:
            return Reply(t(lang, "hr_not_hr"))
        if job_id and db.query(Job.id).filter(Job.id == job_id, Job.owner_id == user.id).first() is None:
            job_id = 0
        available = _analysable_count(db, user.id, job_id or None)
        if not available:
            return Reply(t(lang, "ai_all_none"), [back])
        count = min(available, BULK_ANALYSIS_LIMIT)
        try:
            cfg = ai_provider.resolve_for_user(db, user.id)
            ai_provider.ensure_cv_quota(db, user.id, cfg)
        except ai_provider.AIConfigurationRequiredError:
            return Reply(t(lang, "ai_no_provider"), [back])
        except ai_provider.AIDailyLimitError:
            limit = str(ai_provider.platform_cv_limit() or 0)
            return Reply(t(lang, "ai_daily_limit", limit=limit), [back])
        except AIServiceError:
            return Reply(t(lang, "ai_key_failed"), [back])
        remaining = ai_provider.remaining_cv_checks(db, user.id, cfg)
        if remaining is not None:
            count = min(count, remaining)

        if not confirmed:
            text = t(lang, "ai_all_confirm", count=str(count))
            if available > count:
                text += "\n" + t(lang, "ai_all_limit", limit=str(BULK_ANALYSIS_LIMIT))
            return Reply(
                text,
                [
                    [{"text": t(lang, "btn_ai_all_confirm"), "callback_data": f"hr:aiallok:{job_id}"}],
                    [{"text": t(lang, "btn_cancel"), "callback_data": f"hr:ls:new:{job_id}:0"}],
                ],
            )

        try:
            batch = auto_analyze.create_auto_analyze_batch(
                db, user, count=count, order="oldest", job_id=job_id or None
            )
        except auto_analyze.NoAvailableApplicationsError:
            return Reply(t(lang, "ai_all_none"), [back])
        selected = len(batch.application_ids)
        audit.record(
            db,
            audit.AuditAction.AI_BATCH_STARTED,
            resource_type=audit.AuditResource.AI_ANALYSIS,
            resource_id=batch.id,
            actor=user,
            details={"selected": selected, "order": "oldest", "via": "telegram"},
        )
        outbox_service.record_and_dispatch(db, event_type="dispatch_batch_analysis", payload={"batch_id": batch.id})
        logger.info("AI batch started from Telegram: batch_id=%s user_id=%s selected=%s", batch.id, user.id, selected)
    return Reply(t(lang, "ai_all_started", count=str(selected)), [back])


# ---------------------------------------------------------------------------
# HR: change the status from the bot (phase 4)
# ---------------------------------------------------------------------------

#: Statuses HR can set from the bot, in button order. ``new`` is never a
#: target and ``withdrawn`` belongs to the candidate.
HR_TARGETS = (
    ApplicationStatus.REVIEWING,
    ApplicationStatus.SHORTLISTED,
    ApplicationStatus.INTERVIEW,
    ApplicationStatus.HIRED,
    ApplicationStatus.REJECTED,
)
#: Final decisions ask "are you sure?" first.
CONFIRM_TARGETS = {ApplicationStatus.HIRED, ApplicationStatus.REJECTED}


def hr_set_status(
    profile: TelegramProfile,
    application_id: int,
    target: str,
    page: int = 0,
    *,
    confirmed: bool = False,
) -> Reply:
    """Move an application, exactly like ``PATCH /api/applications/{id}``.

    The same CRUD call writes the status history and queues the candidate's
    notification; the change is audited with the HR user as the actor.
    Hiring and rejecting first return a confirmation card.
    """
    lang = profile.language_code
    try:
        status = ApplicationStatus(target)
    except ValueError:
        return Reply(t(lang, "error"))
    if status not in HR_TARGETS:
        return Reply(t(lang, "error"))

    with SessionLocal() as db:
        user = _hr_for(db, profile)
        if user is None:
            return Reply(t(lang, "hr_not_hr"))
        application = _owned_application(db, user, application_id)
        if application is None:
            return Reply(t(lang, "app_not_found"), [_back_to_list(lang, page)])
        current = _current_status(application)
        if current == ApplicationStatus.WITHDRAWN.value:
            return _hr_card(lang, application, page)
        if current == status.value:
            # A second tap on an old keyboard: nothing to change.
            return _hr_card(lang, application, page)

        label = hr_status_label(lang, status.value)
        if status in CONFIRM_TARGETS and not confirmed:
            text = t(
                lang,
                "hr_confirm",
                name=html.escape(application.name or "—"),
                position=html.escape(application.job.position),
                status=label,
            )
            return Reply(
                text,
                [
                    [{"text": t(lang, "btn_confirm"), "callback_data": f"hr:ok:{application.id}:{status.value}:{page}"}],
                    [{"text": t(lang, "btn_cancel"), "callback_data": f"hr:app:{application.id}:{page}"}],
                ],
            )

        application = application_crud.update_application(
            db, application, ApplicationUpdate(application_status=status)
        )
        audit.record(
            db,
            audit.AuditAction.UPDATE_APPLICATION,
            resource_type=audit.AuditResource.APPLICATION,
            resource_id=application.id,
            actor=user,
            details={
                "fields": ["application_status"],
                "application_status": status.value,
                "via": "telegram",
            },
        )
        logger.info(
            "Application status changed from Telegram: application_id=%s status=%s user_id=%s",
            application.id,
            status.value,
            user.id,
        )
        application = _owned_application(db, user, application_id)
        return _hr_card(lang, application, page, notice=t(lang, "hr_status_set", status=label))


# ---------------------------------------------------------------------------
# HR: schedule an interview from the bot (phase 6)
# ---------------------------------------------------------------------------
#
# Card -> day (hr:iv) -> time (hr:ivd) -> review with duration (hr:ivt)
# -> create (hr:ivok). Every step carries its choices in the callback data,
# so nothing is kept between taps; only the optional meeting link afterwards
# waits for a text message (hr:ivlink, see ``Reply.awaiting_input``).
# Times are picked in ``TELEGRAM_TIMEZONE`` and stored in UTC.

#: Days offered in the day picker.
SCHEDULE_DAYS = 7
#: Start times offered (local time): every 30 minutes, 09:00-18:30.
SLOT_TIMES = tuple(time(hour, minute) for hour in range(9, 19) for minute in (0, 30))
#: Durations offered on the review card, in minutes.
DURATIONS = (30, 45, 60, 90)
DEFAULT_DURATION = 60
#: A slot must start at least this far ahead to be offered or booked.
MIN_LEAD = timedelta(minutes=15)
#: Statuses that end the process: no new interviews for them.
_CLOSED_STATUSES = {
    ApplicationStatus.WITHDRAWN.value,
    ApplicationStatus.HIRED.value,
    ApplicationStatus.REJECTED.value,
}
_DAY_FORMAT = "%Y%m%d"
_SLOT_FORMAT = "%Y%m%d%H%M"


def _now() -> datetime:
    """Current UTC time (a function so tests can move the clock)."""
    return datetime.now(timezone.utc)


def _local_now() -> datetime:
    return _now().astimezone(notifier.local_timezone())


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _next_interview(application: Application) -> Interview | None:
    """The application's soonest upcoming interview that is still ahead."""
    now = _now()
    upcoming = [
        interview
        for interview in application.interviews or []
        if interview.status == InterviewStatus.UPCOMING and _as_utc(interview.scheduled_at) > now
    ]
    return min(upcoming, key=lambda interview: _as_utc(interview.scheduled_at), default=None)


def _free_slots(day: date) -> list[datetime]:
    """The day's start times (local, aware) that are still far enough ahead."""
    tz = notifier.local_timezone()
    earliest = _local_now() + MIN_LEAD
    slots = [datetime.combine(day, slot, tzinfo=tz) for slot in SLOT_TIMES]
    return [slot for slot in slots if slot >= earliest]


def _bookable_days() -> list[date]:
    """The next ``SCHEDULE_DAYS`` days that still have a free slot."""
    today = _local_now().date()
    days = [today + timedelta(days=offset) for offset in range(SCHEDULE_DAYS + 1)]
    return [day for day in days if _free_slots(day)][:SCHEDULE_DAYS]


def _parse_day(value: str) -> date | None:
    try:
        day = datetime.strptime(value, _DAY_FORMAT).date()
    except ValueError:
        return None
    return day if day in _bookable_days() else None


def _parse_slot(value: str) -> datetime | None:
    """A ``YYYYMMDDHHMM`` slot as a local aware datetime, if it is still bookable."""
    try:
        naive = datetime.strptime(value, _SLOT_FORMAT)
    except ValueError:
        return None
    if naive.time() not in SLOT_TIMES:
        return None
    slot = naive.replace(tzinfo=notifier.local_timezone())
    return slot if slot >= _local_now() + MIN_LEAD else None


def _load_schedulable(db, profile: TelegramProfile, application_id: int, page: int):
    """``(user, application, None)`` or ``(None, None, error reply)``."""
    lang = profile.language_code
    user = _hr_for(db, profile)
    if user is None:
        return None, None, Reply(t(lang, "hr_not_hr"))
    application = _owned_application(db, user, application_id)
    if application is None:
        return None, None, Reply(t(lang, "app_not_found"), [_back_to_list(lang, page)])
    if _current_status(application) in _CLOSED_STATUSES:
        return None, None, _hr_card(lang, application, page, notice=t(lang, "iv_closed"))
    return user, application, None


def _schedule_heading(lang: str, application: Application) -> str:
    return t(
        lang,
        "iv_heading",
        name=html.escape(application.name or "—"),
        position=html.escape(application.job.position),
    )


def _day_label(lang: str, day: date) -> str:
    return f"{weekday_label(lang, day.weekday())}, {day.strftime('%d.%m')}"


@dataclass(frozen=True)
class _Target:
    """What a picker step is about, loaded fresh on every tap."""

    user: object
    application: Application
    interview: Interview | None
    heading: str


@dataclass(frozen=True)
class _Flow:
    """One day -> time -> review -> confirm flow and its callback prefixes.

    Scheduling (``hr:iv…``) is keyed by the application id, rescheduling
    (``hr:rs…``, phase 7) by the interview id.
    """

    days: str
    times: str
    review: str
    confirm: str
    confirm_label: str


_SCHEDULE = _Flow("iv", "ivd", "ivt", "ivok", "btn_iv_confirm")
_RESCHEDULE = _Flow("rs", "rsd", "rst", "rsok", "btn_iv_reschedule_confirm")


def _load_target(db, profile: TelegramProfile, flow: _Flow, target_id: int, page: int):
    """``(_Target, None)`` or ``(None, error reply)``."""
    lang = profile.language_code
    if flow is _SCHEDULE:
        user, application, error = _load_schedulable(db, profile, target_id, page)
        if error is not None:
            return None, error
        return _Target(user, application, None, _schedule_heading(lang, application)), None
    user, interview, error = _load_reschedulable(db, profile, target_id, page)
    if error is not None:
        return None, error
    application = interview.candidate
    heading = t(
        lang,
        "iv_reschedule_heading",
        name=html.escape(application.name or "—"),
        position=html.escape(application.job.position),
        date=notifier.format_date(interview.scheduled_at, with_time=True),
    )
    return _Target(user, application, interview, heading), None


def _initial_duration(interview: Interview | None) -> int:
    """Rescheduling keeps the interview's length when the picker offers it."""
    if interview is not None and interview.duration_minutes in DURATIONS:
        return interview.duration_minutes
    return DEFAULT_DURATION


def _pick_day(profile: TelegramProfile, flow: _Flow, target_id: int, page: int, notice: str | None = None) -> Reply:
    lang = profile.language_code
    with SessionLocal() as db:
        target, error = _load_target(db, profile, flow, target_id, page)
        if error is not None:
            return error
        heading, application_id = target.heading, target.application.id

    lines = [notice, ""] if notice else []
    lines += [heading, "", t(lang, "iv_pick_day", tz=html.escape(settings.TELEGRAM_TIMEZONE))]
    days = [
        {"text": _day_label(lang, day), "callback_data": f"hr:{flow.times}:{target_id}:{day.strftime(_DAY_FORMAT)}:{page}"}
        for day in _bookable_days()
    ]
    buttons: Buttons = [days[i : i + 3] for i in range(0, len(days), 3)]
    buttons.append([{"text": t(lang, "btn_cancel"), "callback_data": f"hr:app:{application_id}:{page}"}])
    return Reply("\n".join(lines), buttons)


def _pick_time(profile: TelegramProfile, flow: _Flow, target_id: int, day_value: str, page: int) -> Reply:
    lang = profile.language_code
    day = _parse_day(day_value)
    if day is None:
        return _pick_day(profile, flow, target_id, page, notice=t(lang, "iv_slot_gone"))
    with SessionLocal() as db:
        target, error = _load_target(db, profile, flow, target_id, page)
        if error is not None:
            return error
        heading = target.heading
        duration = _initial_duration(target.interview)

    lines = [heading, "", t(lang, "iv_pick_time", day=_day_label(lang, day))]
    slots = [
        {
            "text": slot.strftime("%H:%M"),
            "callback_data": f"hr:{flow.review}:{target_id}:{slot.strftime(_SLOT_FORMAT)}:{duration}:{page}",
        }
        for slot in _free_slots(day)
    ]
    buttons: Buttons = [slots[i : i + 4] for i in range(0, len(slots), 4)]
    buttons.append([{"text": t(lang, "btn_back_step"), "callback_data": f"hr:{flow.days}:{target_id}:{page}"}])
    return Reply("\n".join(lines), buttons)


def _review(profile: TelegramProfile, flow: _Flow, target_id: int, slot_value: str, duration: int, page: int) -> Reply:
    lang = profile.language_code
    slot = _parse_slot(slot_value)
    if slot is None or duration not in DURATIONS:
        return _pick_day(profile, flow, target_id, page, notice=t(lang, "iv_slot_gone"))
    with SessionLocal() as db:
        target, error = _load_target(db, profile, flow, target_id, page)
        if error is not None:
            return error
        heading = target.heading
        if target.interview is not None:
            interviewer = target.interview.interviewer
        else:
            interviewer = target.user.full_name or target.user.email

    text = "\n".join(
        [
            heading,
            "",
            f"🕒 <b>{notifier.format_date(slot, with_time=True)}</b>",
            t(lang, "iv_duration", minutes=str(duration)),
            t(lang, "iv_interviewer", name=html.escape(interviewer)),
            "",
            t(lang, "iv_review_hint"),
        ]
    )
    durations = [
        {
            "text": f"{'✓ ' if minutes == duration else ''}{t(lang, 'iv_minutes', minutes=str(minutes))}",
            "callback_data": f"hr:{flow.review}:{target_id}:{slot_value}:{minutes}:{page}",
        }
        for minutes in DURATIONS
    ]
    buttons: Buttons = [
        durations,
        [{"text": t(lang, flow.confirm_label), "callback_data": f"hr:{flow.confirm}:{target_id}:{slot_value}:{duration}:{page}"}],
        [{"text": t(lang, "btn_back_step"), "callback_data": f"hr:{flow.times}:{target_id}:{slot_value[:8]}:{page}"}],
    ]
    return Reply(text, buttons)


def hr_schedule_days(profile: TelegramProfile, application_id: int, page: int = 0, notice: str | None = None) -> Reply:
    """Step 1: pick a day."""
    return _pick_day(profile, _SCHEDULE, application_id, page, notice)


def hr_schedule_times(profile: TelegramProfile, application_id: int, day_value: str, page: int = 0) -> Reply:
    """Step 2: pick a start time on the chosen day."""
    return _pick_time(profile, _SCHEDULE, application_id, day_value, page)


def hr_schedule_review(
    profile: TelegramProfile, application_id: int, slot_value: str, duration: int, page: int = 0
) -> Reply:
    """Step 3: the summary, with the duration to choose and the confirm button."""
    return _review(profile, _SCHEDULE, application_id, slot_value, duration, page)


def hr_schedule_confirm(
    profile: TelegramProfile, application_id: int, slot_value: str, duration: int, page: int = 0
) -> Reply:
    """Step 4: create the interview, exactly like ``POST /api/interviews``.

    The HR user is the interviewer and the owner; the creation is audited as
    ``CREATE_INTERVIEW`` with ``via: telegram``. A second tap on the same
    button finds the interview it already created instead of booking twice.
    Reminders follow from the regular reminder scan.
    """
    lang = profile.language_code
    slot = _parse_slot(slot_value)
    if slot is None or duration not in DURATIONS:
        return hr_schedule_days(profile, application_id, page, notice=t(lang, "iv_slot_gone"))
    scheduled_at = slot.astimezone(timezone.utc)

    with SessionLocal() as db:
        user, application, error = _load_schedulable(db, profile, application_id, page)
        if error is not None:
            return error
        interview = (
            db.query(Interview)
            .filter(
                Interview.candidate_id == application.id,
                Interview.status == InterviewStatus.UPCOMING,
                Interview.scheduled_at == scheduled_at,
            )
            .first()
        )
        if interview is None:
            interview = interview_crud.create_interview(
                db,
                InterviewCreate(
                    candidate_id=application.id,
                    interviewer=user.full_name or user.email,
                    scheduled_at=scheduled_at,
                    duration_minutes=duration,
                ),
                application.job.owner_id,
            )
            audit.record(
                db,
                audit.AuditAction.CREATE_INTERVIEW,
                resource_type=audit.AuditResource.INTERVIEW,
                resource_id=interview.id,
                actor=user,
                details={"candidate_id": application.id, "via": "telegram"},
            )
            logger.info(
                "Interview scheduled from Telegram: interview_id=%s application_id=%s user_id=%s",
                interview.id,
                application.id,
                user.id,
            )
        return _scheduled_reply(lang, interview, application, page, t(lang, "iv_scheduled"))


def _scheduled_reply(
    lang: str,
    interview: Interview,
    application: Application,
    page: int,
    title: str,
    hint: str = "iv_reminders_hint",
) -> Reply:
    lines = [
        title,
        "",
        _schedule_heading(lang, application),
        f"🕒 <b>{notifier.format_date(interview.scheduled_at, with_time=True)}</b>",
        t(lang, "iv_duration", minutes=str(interview.duration_minutes)),
    ]
    if interview.meeting_link:
        lines.append(f"🔗 {html.escape(interview.meeting_link)}")
    lines += ["", t(lang, hint)]
    link_key = "btn_change_link" if interview.meeting_link else "btn_add_link"
    buttons: Buttons = [
        [{"text": t(lang, link_key), "callback_data": f"hr:ivlink:{interview.id}:{page}"}],
        [{"text": t(lang, "btn_to_card"), "callback_data": f"hr:app:{application.id}:{page}"}],
    ]
    return Reply("\n".join(lines), buttons)


def _owned_upcoming_interview(db, user, interview_id: int) -> Interview | None:
    interview = interview_crud.get_interview_by_id(db, interview_id, user.id)
    if interview is None or interview.status != InterviewStatus.UPCOMING:
        return None
    if _as_utc(interview.scheduled_at) <= _now():
        return None
    return interview


def hr_meeting_link_prompt(profile: TelegramProfile, interview_id: int, page: int = 0) -> Reply:
    """Ask for the meeting link; the next text message is the answer."""
    lang = profile.language_code
    with SessionLocal() as db:
        user = _hr_for(db, profile)
        if user is None:
            return Reply(t(lang, "hr_not_hr"))
        if _owned_upcoming_interview(db, user, interview_id) is None:
            return Reply(t(lang, "iv_not_found"), [_back_to_list(lang, page)])
    return Reply(t(lang, "iv_link_prompt"), awaiting_input=True)


def _clean_meeting_link(text: str) -> str | None:
    value = (text or "").strip()
    if not value or len(value) > 1024 or any(ch.isspace() for ch in value):
        return None
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    return value


def hr_set_meeting_link(profile: TelegramProfile, interview_id: int, text: str, page: int = 0) -> Reply:
    """Store the meeting link like ``PATCH /api/interviews/{id}`` (audited)."""
    lang = profile.language_code
    link = _clean_meeting_link(text)
    if link is None:
        return Reply(t(lang, "iv_link_invalid"), awaiting_input=True)
    with SessionLocal() as db:
        user = _hr_for(db, profile)
        if user is None:
            return Reply(t(lang, "hr_not_hr"))
        interview = _owned_upcoming_interview(db, user, interview_id)
        if interview is None:
            return Reply(t(lang, "iv_not_found"), [_back_to_list(lang, page)])
        interview = interview_crud.update_interview(db, interview, InterviewUpdate(meeting_link=link))
        audit.record(
            db,
            audit.AuditAction.UPDATE_INTERVIEW,
            resource_type=audit.AuditResource.INTERVIEW,
            resource_id=interview.id,
            actor=user,
            details={"fields": ["meeting_link"], "via": "telegram"},
        )
        return _scheduled_reply(lang, interview, interview.candidate, page, t(lang, "iv_link_saved"))


# ---------------------------------------------------------------------------
# HR: reschedule or cancel an interview from the bot (phase 7)
# ---------------------------------------------------------------------------
#
# Card -> day (hr:rs) -> time (hr:rsd) -> review (hr:rst) -> save (hr:rsok),
# the same pickers as scheduling, keyed by the interview id. Cancelling asks
# first (hr:ivx) and then sets the status (hr:ivxok). Both go through the
# same CRUD call as ``PATCH /api/interviews/{id}``, so the candidate's
# Telegram message and the reminders follow the new state.


def _load_reschedulable(db, profile: TelegramProfile, interview_id: int, page: int):
    """``(user, interview, None)`` or ``(None, None, error reply)``."""
    lang = profile.language_code
    user = _hr_for(db, profile)
    if user is None:
        return None, None, Reply(t(lang, "hr_not_hr"))
    interview = _owned_upcoming_interview(db, user, interview_id)
    if interview is None or interview.candidate is None or interview.candidate.job.owner_id != user.id:
        return None, None, Reply(t(lang, "iv_not_found"), [_back_to_list(lang, page)])
    return user, interview, None


def hr_reschedule_days(profile: TelegramProfile, interview_id: int, page: int = 0, notice: str | None = None) -> Reply:
    return _pick_day(profile, _RESCHEDULE, interview_id, page, notice)


def hr_reschedule_times(profile: TelegramProfile, interview_id: int, day_value: str, page: int = 0) -> Reply:
    return _pick_time(profile, _RESCHEDULE, interview_id, day_value, page)


def hr_reschedule_review(
    profile: TelegramProfile, interview_id: int, slot_value: str, duration: int, page: int = 0
) -> Reply:
    return _review(profile, _RESCHEDULE, interview_id, slot_value, duration, page)


def hr_reschedule_confirm(
    profile: TelegramProfile, interview_id: int, slot_value: str, duration: int, page: int = 0
) -> Reply:
    """Move the interview, like ``PATCH /api/interviews/{id}`` (audited).

    A second tap finds the interview already at that time and changes nothing.
    """
    lang = profile.language_code
    slot = _parse_slot(slot_value)
    if slot is None or duration not in DURATIONS:
        return hr_reschedule_days(profile, interview_id, page, notice=t(lang, "iv_slot_gone"))
    scheduled_at = slot.astimezone(timezone.utc)

    with SessionLocal() as db:
        user, interview, error = _load_reschedulable(db, profile, interview_id, page)
        if error is not None:
            return error
        fields = {}
        if _as_utc(interview.scheduled_at) != scheduled_at:
            fields["scheduled_at"] = scheduled_at
        if interview.duration_minutes != duration:
            fields["duration_minutes"] = duration
        if fields:
            interview = interview_crud.update_interview(db, interview, InterviewUpdate(**fields))
            audit.record(
                db,
                audit.AuditAction.UPDATE_INTERVIEW,
                resource_type=audit.AuditResource.INTERVIEW,
                resource_id=interview.id,
                actor=user,
                details={"fields": sorted(fields), "via": "telegram"},
            )
            logger.info(
                "Interview rescheduled from Telegram: interview_id=%s user_id=%s", interview.id, user.id
            )
        return _scheduled_reply(
            lang, interview, interview.candidate, page, t(lang, "iv_rescheduled"), hint="iv_change_hint"
        )


def hr_cancel_interview(
    profile: TelegramProfile, interview_id: int, page: int = 0, *, confirmed: bool = False
) -> Reply:
    """Ask first, then cancel like ``PATCH /api/interviews/{id}`` with ``status=cancelled``.

    The interview is kept (as cancelled), the application status is left as
    it is, and the candidate hears about it in Telegram when linked.
    """
    lang = profile.language_code
    with SessionLocal() as db:
        user, interview, error = _load_reschedulable(db, profile, interview_id, page)
        if error is not None:
            return error
        application = interview.candidate
        if not confirmed:
            text = t(
                lang,
                "iv_cancel_confirm",
                name=html.escape(application.name or "—"),
                position=html.escape(application.job.position),
                date=notifier.format_date(interview.scheduled_at, with_time=True),
            )
            return Reply(
                text,
                [
                    [{"text": t(lang, "btn_iv_cancel_confirm"), "callback_data": f"hr:ivxok:{interview.id}:{page}"}],
                    [{"text": t(lang, "btn_keep"), "callback_data": f"hr:app:{application.id}:{page}"}],
                ],
            )
        interview_crud.update_interview(db, interview, InterviewUpdate(status=InterviewStatus.CANCELLED))
        audit.record(
            db,
            audit.AuditAction.UPDATE_INTERVIEW,
            resource_type=audit.AuditResource.INTERVIEW,
            resource_id=interview_id,
            actor=user,
            details={"fields": ["status"], "status": InterviewStatus.CANCELLED.value, "via": "telegram"},
        )
        logger.info("Interview cancelled from Telegram: interview_id=%s user_id=%s", interview_id, user.id)
        application = _owned_application(db, user, application.id)
        return _hr_card(lang, application, page, notice=t(lang, "iv_cancelled"))


# ---------------------------------------------------------------------------
# /settings: notification preferences (phase 5)
# ---------------------------------------------------------------------------

#: Switches per account kind, in button order (column ``notify_<key>``).
PREFERENCES: dict[TelegramAccountKind, tuple[str, ...]] = {
    TelegramAccountKind.HR: ("new_applications", "reminders", "analysis"),
    TelegramAccountKind.CANDIDATE: ("status", "reminders"),
}


def settings_page(profile: TelegramProfile) -> Reply:
    """Every switch of every account linked to this Telegram user."""
    lang = profile.language_code
    with SessionLocal() as db:
        links = linking.links_for_telegram_user(db, profile.telegram_user_id)
        if not links:
            return Reply(t(lang, "settings_none"))
        lines = [t(lang, "settings_header")]
        buttons: Buttons = []
        both = len(links) > 1
        for link in sorted(links, key=lambda item: item.kind != TelegramAccountKind.HR):
            heading = "settings_hr" if link.kind == TelegramAccountKind.HR else "settings_candidate"
            lines += ["", t(lang, heading)]
            for key in PREFERENCES[link.kind]:
                mark = "✅" if getattr(link, f"notify_{key}") else "🔕"
                # The candidate's switch also covers interview changes (phase 7).
                text_key = "pref_interviews" if (link.kind, key) == (TelegramAccountKind.CANDIDATE, "reminders") else f"pref_{key}"
                label = f"{mark} {t(lang, text_key)}"
                lines.append(label)
                # With two accounts linked, say which one the button belongs to.
                suffix = f" · {'HR' if link.kind == TelegramAccountKind.HR else '👤'}" if both else ""
                buttons.append([{"text": label + suffix, "callback_data": f"cfg:{link.kind.value}:{key}"}])
    return Reply("\n".join(lines), buttons)


def toggle_setting(profile: TelegramProfile, kind: str, key: str) -> Reply:
    """Flip one switch on this Telegram user's own link, then redraw."""
    try:
        account_kind = TelegramAccountKind(kind)
    except ValueError:
        return Reply(t(profile.language_code, "error"))
    if key not in PREFERENCES[account_kind]:
        return Reply(t(profile.language_code, "error"))
    with SessionLocal() as db:
        for link in linking.links_for_telegram_user(db, profile.telegram_user_id):
            if link.kind == account_kind:
                column = f"notify_{key}"
                setattr(link, column, not getattr(link, column))
                db.commit()
                break
    return settings_page(profile)
