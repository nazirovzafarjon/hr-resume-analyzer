"""Telegram bot phase 9: /jobs, /interviews (mark completed, notes) and /stats for HR."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.bot import actions, handlers
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.application import AnalysisStatus, Application, ApplicationStatus
from app.models.audit_log import AuditLog
from app.models.interview import Interview, InterviewStatus
from app.services.telegram import notifier
from tests.payloads import JOB_PAYLOAD
from tests.test_telegram_hr_notifications import (
    HR_TG,
    OTHER_TG,
    _add_application,
    _create_job,
    _link_hr,
    _profile,
)

#: Tuesday 1 December 2026, 10:00 in Tashkent (UTC+5).
NOW = datetime(2026, 12, 1, 5, 0, tzinfo=timezone.utc)
TODAY_MORNING = datetime(2026, 12, 1, 2, 0, tzinfo=timezone.utc)  # 07:00 local, already over
TODAY_AFTERNOON = datetime(2026, 12, 1, 10, 0, tzinfo=timezone.utc)  # 15:00 local
TOMORROW = datetime(2026, 12, 2, 6, 0, tzinfo=timezone.utc)  # 11:00 local
IN_THREE_DAYS = datetime(2026, 12, 4, 4, 0, tzinfo=timezone.utc)
IN_TEN_DAYS = datetime(2026, 12, 11, 4, 0, tzinfo=timezone.utc)
TWO_DAYS_AGO = datetime(2026, 11, 29, 10, 0, tzinfo=timezone.utc)


@pytest.fixture
def telegram_on(monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_ENABLED", True)
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "123:test-token")
    monkeypatch.setattr(settings, "TELEGRAM_BOT_USERNAME", "ra_test_bot")
    monkeypatch.setattr(settings, "TELEGRAM_TIMEZONE", "Asia/Tashkent")


@pytest.fixture
def clock(monkeypatch):
    monkeypatch.setattr(actions, "_now", lambda: NOW)
    monkeypatch.setattr(notifier, "_utcnow", lambda: NOW)
    return NOW


@pytest.fixture
def hr(user, telegram_on, clock):
    _link_hr(user["id"])
    return user


@pytest.fixture
def job(client, user):
    return _create_job(client, user["headers"])


def _callbacks(reply):
    return [button["callback_data"] for row in reply.buttons for button in row if "callback_data" in button]


def _urls(reply):
    return [button["url"] for row in reply.buttons for button in row if "url" in button]


def _interview(application_id, hr_id, when, status=InterviewStatus.UPCOMING, **fields):
    with SessionLocal() as db:
        interview = Interview(
            candidate_id=application_id,
            hr_id=hr_id,
            interviewer="Alice HR",
            scheduled_at=when,
            duration_minutes=45,
            status=status,
            **fields,
        )
        db.add(interview)
        db.commit()
        return interview.id


# --- /jobs -------------------------------------------------------------------------


def test_jobs_require_an_hr_link(telegram_on):
    assert "HR uchun" in actions.hr_jobs(_profile()).text
    assert "HR uchun" in actions.hr_job_detail(_profile(), 1).text


def test_jobs_list_own_jobs_with_counts(client, hr, other_user):
    first = _create_job(client, hr["headers"], position="Backend")
    second = _create_job(client, hr["headers"], position="Designer")
    _create_job(client, other_user["headers"], position="Not yours")
    _add_application(first["id"])
    _add_application(first["id"], status=ApplicationStatus.SHORTLISTED)

    reply = actions.hr_jobs(_profile())
    assert "Not yours" not in reply.text
    assert "2 ta ariza, 1 ta yangi" in reply.text and "0 ta ariza, 0 ta yangi" in reply.text
    # Newest first.
    assert reply.text.index("Designer") < reply.text.index("Backend")
    assert _callbacks(reply)[:2] == [f"hr:job:{second['id']}:0", f"hr:job:{first['id']}:0"]


def test_jobs_pages(client, hr):
    for n in range(6):
        _create_job(client, hr["headers"], position=f"Role {n}")
    first = actions.hr_jobs(_profile())
    assert "(6 ta) — 1/2" in first.text and "hr:jl:1" in _callbacks(first)
    assert "2/2" in actions.hr_jobs(_profile(), 1).text


def test_job_detail(client, hr, job, monkeypatch):
    monkeypatch.setattr(settings, "FRONTEND_BASE_URL", "https://hr.example.com")
    new_id = _add_application(job["id"], name="Fresh")
    _add_application(job["id"], status=ApplicationStatus.INTERVIEW)
    with SessionLocal() as db:
        application = db.get(Application, new_id)
        application.analysis_status = AnalysisStatus.COMPLETED
        application.ai_score = 80
        db.commit()
    _interview(new_id, hr["id"], TOMORROW)
    _interview(new_id, hr["id"], TWO_DAYS_AGO)

    reply = actions.hr_job_detail(_profile(), job["id"], page=2)
    token = job["application_form"]["public_token"]
    assert "Arizalar: <b>2</b>" in reply.text
    assert "Yangi: 1" in reply.text and "Suhbat: 1" in reply.text
    assert "Tahlil qilingan: 1 · o'rtacha moslik 80%" in reply.text
    assert "Kelgusi suhbatlar: 1" in reply.text
    assert f"https://hr.example.com/apply/{token}" in reply.text
    callbacks = _callbacks(reply)
    assert f"hr:ls:all:{job['id']}:0" in callbacks and f"hr:ls:new:{job['id']}:0" in callbacks
    assert callbacks[-1] == "hr:jl:2"
    assert _urls(reply) == [f"https://hr.example.com/apply/{token}", f"https://hr.example.com/jobs/{job['id']}"]


def test_job_detail_without_a_form_or_public_site(client, hr):
    response = client.post("/api/jobs", json=JOB_PAYLOAD, headers=hr["headers"])
    job_id = response.json()["id"]
    reply = actions.hr_job_detail(_profile(), job_id)
    assert "hali e'lon qilinmagan" in reply.text
    assert _urls(reply) == []  # localhost cannot be opened from Telegram


def test_job_detail_offers_bulk_analysis(hr, job):
    _add_application(job["id"])
    assert f"hr:aiall:{job['id']}" in _callbacks(actions.hr_job_detail(_profile(), job["id"]))


def test_other_hrs_job_is_not_shown(client, hr, other_user):
    foreign = _create_job(client, other_user["headers"])
    assert "topilmadi" in actions.hr_job_detail(_profile(), foreign["id"]).text


# --- /interviews -------------------------------------------------------------------


@pytest.fixture
def interviews(client, hr, other_user, job):
    application_id = _add_application(job["id"], name="Jane Doe")
    ids = {
        name: _interview(application_id, hr["id"], when)
        for name, when in (
            ("morning", TODAY_MORNING),
            ("afternoon", TODAY_AFTERNOON),
            ("tomorrow", TOMORROW),
            ("in3", IN_THREE_DAYS),
            ("in10", IN_TEN_DAYS),
            ("two_days_ago", TWO_DAYS_AGO),
        )
    }
    ids["completed"] = _interview(application_id, hr["id"], TWO_DAYS_AGO, status=InterviewStatus.COMPLETED)
    ids["cancelled"] = _interview(application_id, hr["id"], TODAY_AFTERNOON, status=InterviewStatus.CANCELLED)
    foreign_job = _create_job(client, other_user["headers"])
    ids["foreign"] = _interview(_add_application(foreign_job["id"]), other_user["id"], TODAY_AFTERNOON)
    ids["application"] = application_id
    return ids


def _listed(reply):
    return [int(c.split(":")[2]) for c in _callbacks(reply) if c.startswith("hr:ivc:")]


def test_interview_tabs(interviews):
    ids = interviews
    assert _listed(actions.hr_interviews(_profile(), "today")) == [ids["morning"], ids["afternoon"]]
    assert _listed(actions.hr_interviews(_profile(), "tomorrow")) == [ids["tomorrow"]]
    assert _listed(actions.hr_interviews(_profile(), "week")) == [ids["afternoon"], ids["tomorrow"], ids["in3"]]
    # Over without an outcome, newest first; completed and cancelled ones are done.
    assert _listed(actions.hr_interviews(_profile(), "past")) == [ids["morning"], ids["two_days_ago"]]


def test_interview_list_text_and_tabs(interviews):
    reply = actions.hr_interviews(_profile(), "today")
    assert "Suhbatlar: Bugun" in reply.text and "(2 ta)" in reply.text
    assert "07:00" in reply.text and "15:00" in reply.text and "Jane Doe" in reply.text
    assert "• Bugun" in str(reply.buttons)
    for tab in actions.INTERVIEW_TABS:
        assert f"hr:ivl:{tab}:0" in _callbacks(reply)
    week = actions.hr_interviews(_profile(), "week")
    assert "02.12.2026 11:00" in week.text  # several days: the date is shown


def test_empty_tabs(hr):
    assert "suhbat yo'q" in actions.hr_interviews(_profile(), "tomorrow").text
    assert "Natijasi belgilanmagan" in actions.hr_interviews(_profile(), "past").text
    assert "Bugun" in actions.hr_interviews(_profile(), "bogus").text


def test_card_of_an_upcoming_interview(interviews):
    reply = actions.hr_interview_card(_profile(), interviews["afternoon"], "week", 1)
    callbacks = _callbacks(reply)
    iid = interviews["afternoon"]
    assert "Kutilmoqda" in reply.text and "Alice HR" in reply.text
    assert f"hr:rs:{iid}:0" in callbacks and f"hr:ivx:{iid}:0" in callbacks and f"hr:ivlink:{iid}:0" in callbacks
    assert not any(c.startswith("hr:ivdone:") for c in callbacks)
    assert f"hr:app:{interviews['application']}:0" in callbacks and callbacks[-1] == "hr:ivl:week:1"


def test_card_of_a_past_interview_offers_completion(interviews):
    reply = actions.hr_interview_card(_profile(), interviews["morning"], "past", 0)
    callbacks = _callbacks(reply)
    assert "natija belgilanmagan" in reply.text
    assert f"hr:ivdone:{interviews['morning']}:past:0" in callbacks
    assert not any(c.startswith(("hr:rs:", "hr:ivx:")) for c in callbacks)


def test_mark_completed(interviews):
    iid = interviews["morning"]
    reply = actions.hr_interview_done(_profile(), iid, "past", 0)
    assert "o'tkazildi deb belgilandi" in reply.text and "O'tkazildi" in reply.text
    with SessionLocal() as db:
        assert db.get(Interview, iid).status == InterviewStatus.COMPLETED
        entry = db.query(AuditLog).filter(AuditLog.action == "UPDATE_INTERVIEW").one()
        assert entry.details == {"fields": ["status"], "status": "completed", "via": "telegram"}
    # Gone from the "no outcome" tab; a second tap changes nothing.
    assert iid not in _listed(actions.hr_interviews(_profile(), "past"))
    actions.hr_interview_done(_profile(), iid, "past", 0)
    with SessionLocal() as db:
        assert db.query(AuditLog).filter(AuditLog.action == "UPDATE_INTERVIEW").count() == 1


def test_cannot_complete_before_the_start(interviews):
    reply = actions.hr_interview_done(_profile(), interviews["afternoon"], "today", 0)
    assert "hali boshlanmagan" in reply.text
    with SessionLocal() as db:
        assert db.get(Interview, interviews["afternoon"]).status == InterviewStatus.UPCOMING


def test_notes_are_appended_and_audited(interviews):
    iid = interviews["afternoon"]
    with SessionLocal() as db:
        db.get(Interview, iid).notes = "Written in the CRM"
        db.commit()
    assert actions.hr_note_prompt(_profile(), iid, "today", 0).awaiting_input

    reply = actions.hr_add_note(_profile(), iid, "  Strong <SQL> skills  ", "today", 0)
    assert "Izoh qo'shildi" in reply.text and "Strong &lt;SQL&gt; skills" in reply.text
    with SessionLocal() as db:
        notes = db.get(Interview, iid).notes
        assert notes == "Written in the CRM\n\n[01.12.2026 10:00 · Telegram] Strong <SQL> skills"
        entry = db.query(AuditLog).filter(AuditLog.action == "UPDATE_INTERVIEW").one()
        assert entry.details == {"fields": ["notes"], "via": "telegram"}


@pytest.mark.parametrize("text", ["", "   ", "x" * (actions.NOTE_LIMIT + 1)])
def test_invalid_notes_ask_again(interviews, text):
    reply = actions.hr_add_note(_profile(), interviews["afternoon"], text)
    assert reply.awaiting_input
    with SessionLocal() as db:
        assert db.get(Interview, interviews["afternoon"]).notes is None


def test_cancelled_interview_takes_no_notes(interviews):
    reply = actions.hr_note_prompt(_profile(), interviews["cancelled"], "today", 0)
    assert not reply.awaiting_input and "Bekor qilingan" in reply.text
    assert not any(c.startswith("hr:ivnote:") for c in _callbacks(reply))


def test_other_hr_cannot_see_or_change_an_interview(interviews, other_user):
    _link_hr(other_user["id"], telegram_user_id=OTHER_TG)
    profile = _profile(OTHER_TG)
    assert "topilmadi" in actions.hr_interview_card(profile, interviews["morning"]).text
    assert "topilmadi" in actions.hr_interview_done(profile, interviews["morning"]).text
    assert "topilmadi" in actions.hr_add_note(profile, interviews["morning"], "hi").text
    assert interviews["morning"] not in _listed(actions.hr_interviews(profile, "past"))
    with SessionLocal() as db:
        interview = db.get(Interview, interviews["morning"])
        assert interview.status == InterviewStatus.UPCOMING and interview.notes is None


# --- /stats ------------------------------------------------------------------------


def test_stats(hr, job):
    first = _add_application(job["id"])
    _add_application(job["id"], status=ApplicationStatus.HIRED)
    with SessionLocal() as db:
        application = db.get(Application, first)
        application.analysis_status = AnalysisStatus.COMPLETED
        application.ai_score = 70
        db.commit()

    reply = actions.hr_stats(_profile(), "30d")
    assert "oxirgi 30 kun" in reply.text
    assert "Yangi arizalar: <b>2</b> (↑" in reply.text
    assert "1 ta vakansiya · 2 ta ariza" in reply.text
    assert "Yangi: 1" in reply.text and "Ishga olindi: 1" in reply.text
    assert "AI tahlil qilingan: 1 · o'rtacha moslik 70%" in reply.text
    assert "1. Backend Developer — Acme Corp (2)" in reply.text
    assert _callbacks(reply) == ["hr:st:7d", "hr:st:30d", "hr:st:90d"]
    assert "• 30 kun" in str(reply.buttons)


def test_stats_with_no_data_and_bad_range(hr):
    reply = actions.hr_stats(_profile(), "1y")
    assert "oxirgi 7 kun" in reply.text and "Yangi arizalar: <b>0</b> (—" in reply.text


def test_stats_require_an_hr_link(telegram_on):
    assert "HR uchun" in actions.hr_stats(_profile()).text


@pytest.mark.parametrize(
    "current,previous,expected", [(0, 0, "—"), (3, 0, "↑"), (6, 3, "↑ 100%"), (2, 4, "↓ 50%"), (5, 5, "→ 0%")]
)
def test_change_wording(current, previous, expected):
    assert actions._change(current, previous) == expected


# --- home screen, texts, handlers --------------------------------------------------------


def test_home_screen_offers_phase_9_sections(hr):
    callbacks = [b["callback_data"] for row in actions.home_buttons(_profile()) for b in row]
    for data in ("hr:jl:0", "hr:ivl:today:0", "hr:st:7d"):
        assert data in callbacks


def test_texts_exist_in_every_language(interviews):
    for lang, word in (("ru", "Собеседования"), ("en", "Interviews")):
        assert word in actions.hr_interviews(_profile(language_code=lang)).text
    for lang, word in (("ru", "Вакансии"), ("en", "Jobs")):
        assert word in actions.hr_jobs(_profile(language_code=lang)).text
    for lang, word in (("ru", "Статистика"), ("en", "Stats")):
        assert word in actions.hr_stats(_profile(language_code=lang)).text


def _query(data):
    user = MagicMock(id=HR_TG, username="hr", first_name="Hana", language_code="uz")
    query = MagicMock(data=data, from_user=user)
    query.answer = AsyncMock()
    query.message.chat.id = HR_TG
    query.message.edit_text = AsyncMock()
    query.message.answer = AsyncMock()
    return query


def _state(data=None):
    state = MagicMock()
    state.set_state = AsyncMock()
    state.update_data = AsyncMock()
    state.get_data = AsyncMock(return_value=data or {})
    return state


def test_note_button_and_reply_through_the_handlers(interviews):
    iid = interviews["afternoon"]
    query, state = _query(f"hr:ivnote:{iid}:week:1"), _state()
    asyncio.run(handlers.on_hr_callback(query, state))
    state.set_state.assert_awaited_with(handlers.InterviewNote.waiting)
    state.update_data.assert_awaited_once_with(note_interview_id=iid, note_tab="week", note_page=1)
    query.message.edit_text.assert_not_awaited()  # the card stays; the question comes below

    message = MagicMock(text="Great fit")
    message.from_user = MagicMock(id=HR_TG, username="hr", first_name="Hana", language_code="uz")
    message.chat.id = HR_TG
    message.answer = AsyncMock()
    state = _state({"note_interview_id": iid, "note_tab": "week", "note_page": 1})
    asyncio.run(handlers.on_interview_note(message, state))
    assert "Izoh qo'shildi" in message.answer.await_args.args[0]
    state.set_state.assert_awaited_once_with(None)


def test_stats_button_through_the_handler(hr):
    query = _query("hr:st:90d")
    asyncio.run(handlers.on_hr_callback(query, _state()))
    assert "oxirgi 90 kun" in query.message.edit_text.await_args.args[0]
    query.answer.assert_awaited_once()
