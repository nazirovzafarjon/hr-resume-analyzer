"""Telegram bot phase 6: HR schedules an interview from the bot."""

from datetime import datetime, timedelta, timezone

import pytest

from app.bot import actions
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.application import ApplicationStatus
from app.models.audit_log import AuditLog
from app.models.interview import Interview, InterviewStatus
from app.models.user import User
from tests.test_telegram_hr_notifications import (
    OTHER_TG,
    _add_application,
    _create_job,
    _link_hr,
    _profile,
)

#: Tuesday 1 December 2026, 10:00 in Tashkent (UTC+5).
NOW = datetime(2026, 12, 1, 5, 0, tzinfo=timezone.utc)
#: Wednesday 2 December 2026, 14:00 Tashkent = 09:00 UTC.
SLOT = "202612021400"
SLOT_UTC = datetime(2026, 12, 2, 9, 0, tzinfo=timezone.utc)


@pytest.fixture
def telegram_on(monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_ENABLED", True)
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "123:test-token")
    monkeypatch.setattr(settings, "TELEGRAM_BOT_USERNAME", "ra_test_bot")
    monkeypatch.setattr(settings, "TELEGRAM_TIMEZONE", "Asia/Tashkent")


@pytest.fixture
def clock(monkeypatch):
    monkeypatch.setattr(actions, "_now", lambda: NOW)
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


def _interviews(application_id):
    with SessionLocal() as db:
        return db.query(Interview).filter(Interview.candidate_id == application_id).all()


def _book(application_id, slot=SLOT, duration=60, page=0):
    return actions.hr_schedule_confirm(_profile(), application_id, slot, duration, page)


# --- the HR card -----------------------------------------------------------------


def test_card_offers_scheduling(hr, job):
    application_id = _add_application(job["id"])
    reply = actions.hr_application_detail(_profile(), application_id, page=3)
    assert _callbacks(reply)[0] == f"hr:iv:{application_id}:3"
    assert "Suhbat belgilash" in str(reply.buttons)


@pytest.mark.parametrize(
    "status", [ApplicationStatus.WITHDRAWN, ApplicationStatus.HIRED, ApplicationStatus.REJECTED]
)
def test_closed_applications_cannot_be_scheduled(hr, job, status):
    application_id = _add_application(job["id"], status=status)
    card = actions.hr_application_detail(_profile(), application_id)
    assert not any(c.startswith("hr:iv:") for c in _callbacks(card))

    reply = _book(application_id)
    assert "yopilgan" in reply.text
    assert _interviews(application_id) == []


def test_card_shows_the_next_interview(hr, job):
    application_id = _add_application(job["id"])
    _book(application_id)
    reply = actions.hr_application_detail(_profile(), application_id)
    assert "02.12.2026 14:00" in reply.text


# --- pickers ---------------------------------------------------------------------


def test_day_picker_offers_seven_days_from_today(hr, job):
    application_id = _add_application(job["id"])
    reply = actions.hr_schedule_days(_profile(), application_id, page=2)
    days = [c for c in _callbacks(reply) if c.startswith("hr:ivd:")]
    assert days[0] == f"hr:ivd:{application_id}:20261201:2"
    assert days[-1] == f"hr:ivd:{application_id}:20261207:2"
    assert len(days) == 7
    assert "Se, 01.12" in str(reply.buttons)  # Tuesday in Uzbek
    assert "Asia/Tashkent" in reply.text
    assert _callbacks(reply)[-1] == f"hr:app:{application_id}:2"


def test_day_without_free_slots_is_skipped(hr, job, monkeypatch):
    # 18:30 Tashkent: today's last slot is too close, so the list starts tomorrow.
    monkeypatch.setattr(actions, "_now", lambda: datetime(2026, 12, 1, 13, 30, tzinfo=timezone.utc))
    application_id = _add_application(job["id"])
    days = [c for c in _callbacks(actions.hr_schedule_days(_profile(), application_id)) if c.startswith("hr:ivd:")]
    assert days[0].endswith(":20261202:0") and len(days) == 7


def test_time_picker_skips_past_slots(hr, job):
    application_id = _add_application(job["id"])
    today = _callbacks(actions.hr_schedule_times(_profile(), application_id, "20261201"))
    slots = [c.split(":")[3] for c in today if c.startswith("hr:ivt:")]
    # 10:00 now, 15 minutes lead: the first free slot is 10:30.
    assert slots[0] == "202612011030" and slots[-1] == "202612011830"

    tomorrow = _callbacks(actions.hr_schedule_times(_profile(), application_id, "20261202"))
    slots = [c for c in tomorrow if c.startswith("hr:ivt:")]
    assert len(slots) == 20
    assert f"hr:ivt:{application_id}:{SLOT}:60:0" in slots


@pytest.mark.parametrize("day", ["20261130", "20261209", "garbage"])
def test_time_picker_rejects_days_outside_the_range(hr, job, day):
    application_id = _add_application(job["id"])
    reply = actions.hr_schedule_times(_profile(), application_id, day)
    assert "mavjud emas" in reply.text
    assert not any(c.startswith("hr:ivt:") for c in _callbacks(reply))


def test_review_shows_summary_and_durations(hr, job):
    application_id = _add_application(job["id"], name="<Jane>")
    reply = actions.hr_schedule_review(_profile(), application_id, SLOT, 45, page=1)
    assert "02.12.2026 14:00" in reply.text and "45 daqiqa" in reply.text
    assert "&lt;Jane&gt;" in reply.text
    callbacks = _callbacks(reply)
    for minutes in actions.DURATIONS:
        assert f"hr:ivt:{application_id}:{SLOT}:{minutes}:1" in callbacks
    assert f"hr:ivok:{application_id}:{SLOT}:45:1" in callbacks
    assert callbacks[-1] == f"hr:ivd:{application_id}:20261202:1"
    assert "✓ 45 daq" in str(reply.buttons)


@pytest.mark.parametrize(
    "slot, duration",
    [
        ("202612011000", 60),  # now: too soon
        ("202612021415", 60),  # not one of the offered times
        (SLOT, 25),  # duration not offered
    ],
)
def test_invalid_choices_go_back_to_the_day_picker(hr, job, slot, duration):
    application_id = _add_application(job["id"])
    reply = _book(application_id, slot, duration)
    assert "mavjud emas" in reply.text
    assert _interviews(application_id) == []


# --- booking ---------------------------------------------------------------------


def test_confirm_creates_the_interview_and_audits(hr, job):
    application_id = _add_application(job["id"])

    reply = _book(application_id, duration=90, page=2)

    [interview] = _interviews(application_id)
    assert interview.scheduled_at.astimezone(timezone.utc) == SLOT_UTC
    assert interview.duration_minutes == 90
    assert interview.status == InterviewStatus.UPCOMING
    assert interview.hr_id == hr["id"]
    with SessionLocal() as db:
        assert interview.interviewer == db.get(User, hr["id"]).full_name
        entry = (
            db.query(AuditLog)
            .filter(AuditLog.action == "CREATE_INTERVIEW", AuditLog.resource_id == str(interview.id))
            .one()
        )
        assert entry.actor_user_id == hr["id"]
        assert entry.details["candidate_id"] == application_id
        assert entry.details["via"] == "telegram"

    assert "Suhbat belgilandi" in reply.text and "02.12.2026 14:00" in reply.text
    assert _callbacks(reply) == [f"hr:ivlink:{interview.id}:2", f"hr:app:{application_id}:2"]


def test_repeated_confirm_books_once(hr, job):
    application_id = _add_application(job["id"])
    _book(application_id)
    reply = _book(application_id)
    assert len(_interviews(application_id)) == 1
    assert "Suhbat belgilandi" in reply.text


def test_scheduling_does_not_change_the_application_status(hr, job):
    application_id = _add_application(job["id"], status=ApplicationStatus.SHORTLISTED)
    _book(application_id)
    card = actions.hr_application_detail(_profile(), application_id)
    assert "Tanlangan" in card.text


def test_other_hr_cannot_schedule(client, hr, other_user, job):
    _link_hr(other_user["id"], telegram_user_id=OTHER_TG)
    application_id = _add_application(job["id"])
    reply = actions.hr_schedule_confirm(_profile(OTHER_TG), application_id, SLOT, 60, 0)
    assert "topilmadi" in reply.text
    assert _interviews(application_id) == []


def test_scheduling_requires_an_hr_link(telegram_on, clock, user, job):
    application_id = _add_application(job["id"])
    reply = actions.hr_schedule_days(_profile(), application_id)
    assert "HR uchun" in reply.text


def test_booked_interview_gets_reminders(hr, job):
    from app.services.telegram import notifier

    application_id = _add_application(job["id"])
    _book(application_id)
    with SessionLocal() as db:
        events = notifier.scan_interview_reminders(db, now=SLOT_UTC - timedelta(hours=23))
        assert [e.payload["audience"] for e in events] == ["hr"]


# --- meeting link ----------------------------------------------------------------


def _booked(application_id):
    _book(application_id)
    return _interviews(application_id)[0].id


def test_link_prompt_waits_for_input(hr, job):
    interview_id = _booked(_add_application(job["id"]))
    reply = actions.hr_meeting_link_prompt(_profile(), interview_id)
    assert reply.awaiting_input and "/cancel" in reply.text


def test_valid_link_is_saved_and_audited(hr, job):
    application_id = _add_application(job["id"])
    interview_id = _booked(application_id)

    reply = actions.hr_set_meeting_link(_profile(), interview_id, "  https://meet.example.com/abc  ", page=1)

    assert not reply.awaiting_input
    assert "Havola saqlandi" in reply.text and "https://meet.example.com/abc" in reply.text
    assert _callbacks(reply) == [f"hr:ivlink:{interview_id}:1", f"hr:app:{application_id}:1"]
    assert "Havolani o'zgartirish" in str(reply.buttons)
    with SessionLocal() as db:
        assert db.get(Interview, interview_id).meeting_link == "https://meet.example.com/abc"
        entry = (
            db.query(AuditLog)
            .filter(AuditLog.action == "UPDATE_INTERVIEW", AuditLog.resource_id == str(interview_id))
            .one()
        )
        assert entry.details["fields"] == ["meeting_link"]
        assert entry.details["via"] == "telegram"


@pytest.mark.parametrize("text", ["hello", "ftp://example.com", "javascript:alert(1)", "https://a b.com", ""])
def test_invalid_link_asks_again(hr, job, text):
    interview_id = _booked(_add_application(job["id"]))
    reply = actions.hr_set_meeting_link(_profile(), interview_id, text)
    assert reply.awaiting_input and "https://" in reply.text
    with SessionLocal() as db:
        assert db.get(Interview, interview_id).meeting_link is None


def test_link_cannot_be_set_on_another_hrs_interview(client, hr, other_user, job):
    _link_hr(other_user["id"], telegram_user_id=OTHER_TG)
    interview_id = _booked(_add_application(job["id"]))
    assert "topilmadi" in actions.hr_meeting_link_prompt(_profile(OTHER_TG), interview_id).text
    reply = actions.hr_set_meeting_link(_profile(OTHER_TG), interview_id, "https://evil.example.com")
    assert not reply.awaiting_input and "topilmadi" in reply.text
    with SessionLocal() as db:
        assert db.get(Interview, interview_id).meeting_link is None


def test_link_cannot_be_set_on_a_cancelled_interview(hr, job):
    interview_id = _booked(_add_application(job["id"]))
    with SessionLocal() as db:
        db.get(Interview, interview_id).status = InterviewStatus.CANCELLED
        db.commit()
    reply = actions.hr_set_meeting_link(_profile(), interview_id, "https://meet.example.com/abc")
    assert "topilmadi" in reply.text


def test_texts_exist_in_every_language(hr, job):
    application_id = _add_application(job["id"])
    for lang, word in (("ru", "Назначить"), ("en", "Schedule")):
        reply = actions.hr_application_detail(_profile(language_code=lang), application_id)
        assert word in str(reply.buttons)
