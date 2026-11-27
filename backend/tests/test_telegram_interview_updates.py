"""Telegram bot phase 7: candidates hear about interview changes; HR reschedules and cancels."""

from datetime import datetime, timedelta, timezone

import pytest

from app.bot import actions
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.audit_log import AuditLog
from app.models.interview import Interview, InterviewStatus
from app.models.outbox import OutboxEvent
from app.models.telegram_link import TelegramAccountKind, TelegramLink
from app.services.telegram import notifier
from tests.test_telegram_hr_notifications import HR_TG, OTHER_TG, _link_hr
from tests.test_telegram_hr_notifications import _profile as _hr_profile
from tests.test_telegram_notifications import TG_USER, _apply, _link, _register_candidate
from tests.test_telegram_notifications import _profile as _candidate_profile

#: Tuesday 1 December 2026, 10:00 in Tashkent (UTC+5).
NOW = datetime(2026, 12, 1, 5, 0, tzinfo=timezone.utc)
#: Wednesday 2 December 2026, 14:00 Tashkent = 09:00 UTC.
SLOT_UTC = datetime(2026, 12, 2, 9, 0, tzinfo=timezone.utc)
#: Thursday 3 December 2026, 11:30 Tashkent = 06:30 UTC.
NEW_SLOT = "202612031130"
NEW_SLOT_UTC = datetime(2026, 12, 3, 6, 30, tzinfo=timezone.utc)


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
def sent(monkeypatch):
    from app.services.telegram import client as tg_client

    messages: list[dict] = []

    def fake_send(chat_id, text, *, buttons=None):
        messages.append({"chat_id": chat_id, "text": text, "buttons": buttons or []})
        return {"message_id": len(messages)}

    monkeypatch.setattr(tg_client, "send_message", fake_send)
    return messages


@pytest.fixture
def job(client, user):
    from tests.payloads import JOB_PAYLOAD

    response = client.post("/api/jobs", json=JOB_PAYLOAD, headers=user["headers"])
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def application_id(client, telegram_on, clock, sent, job):
    """An application from a candidate account linked to Telegram (no messages yet)."""
    candidate_id = _register_candidate(client, "jane@example.com")
    application_id = _apply(job["id"], candidate_id)
    _link(candidate_id)
    sent.clear()
    return application_id


def _schedule(client, user, application_id, when=SLOT_UTC, **fields):
    payload = {
        "candidate_id": application_id,
        "interviewer": "Alice HR",
        "scheduled_at": when.isoformat(),
        "duration_minutes": 45,
        **fields,
    }
    response = client.post("/api/interviews", json=payload, headers=user["headers"])
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _patch(client, user, interview_id, **fields):
    response = client.patch(f"/api/interviews/{interview_id}", json=fields, headers=user["headers"])
    assert response.status_code == 200, response.text


def _to_candidate(sent):
    return [message for message in sent if message["chat_id"] == TG_USER]


# --- candidate notifications ------------------------------------------------------


def test_scheduling_tells_the_candidate(client, user, application_id, sent):
    _schedule(client, user, application_id, meeting_link="https://meet.example.com/x")

    [message] = _to_candidate(sent)
    assert "suhbatga taklif qilindingiz" in message["text"]
    assert "02.12.2026 14:00" in message["text"]
    assert "45 daqiqa" in message["text"]
    assert "https://meet.example.com/x" in message["text"]
    assert message["buttons"][0][0]["callback_data"] == f"app:{application_id}:0"


def test_moving_tells_the_new_and_old_time(client, user, application_id, sent):
    interview_id = _schedule(client, user, application_id)
    sent.clear()
    _patch(client, user, interview_id, scheduled_at=NEW_SLOT_UTC.isoformat())

    [message] = _to_candidate(sent)
    assert "vaqti o'zgardi" in message["text"]
    assert "03.12.2026 11:30" in message["text"]
    assert "<s>02.12.2026 14:00</s>" in message["text"]


def test_cancelling_tells_the_candidate(client, user, application_id, sent):
    interview_id = _schedule(client, user, application_id)
    sent.clear()
    _patch(client, user, interview_id, status="cancelled")

    [message] = _to_candidate(sent)
    assert "bekor qilindi" in message["text"] and "02.12.2026 14:00" in message["text"]


def test_deleting_an_upcoming_interview_tells_the_candidate(client, user, application_id, sent):
    interview_id = _schedule(client, user, application_id)
    sent.clear()
    response = client.delete(f"/api/interviews/{interview_id}", headers=user["headers"])
    assert response.status_code == 204

    [message] = _to_candidate(sent)
    assert "bekor qilindi" in message["text"]


def test_reinstating_a_cancelled_interview_invites_again(client, user, application_id, sent):
    interview_id = _schedule(client, user, application_id)
    _patch(client, user, interview_id, status="cancelled")
    sent.clear()
    _patch(client, user, interview_id, status="upcoming")

    [message] = _to_candidate(sent)
    assert "taklif qilindingiz" in message["text"]


def test_adding_a_meeting_link_tells_the_candidate(client, user, application_id, sent):
    interview_id = _schedule(client, user, application_id)
    sent.clear()
    _patch(client, user, interview_id, meeting_link="https://zoom.example.com/j/1")

    [message] = _to_candidate(sent)
    assert "havolasi qo'shildi" in message["text"] and "https://zoom.example.com/j/1" in message["text"]


@pytest.mark.parametrize(
    "fields",
    [
        {"notes": "Bring the portfolio"},
        {"interviewer": "Bob"},
        {"duration_minutes": 90},
        {"meeting_link": "not a link"},
        {"status": "completed"},
    ],
)
def test_internal_edits_send_nothing(client, user, application_id, sent, fields):
    interview_id = _schedule(client, user, application_id)
    sent.clear()
    _patch(client, user, interview_id, **fields)
    assert _to_candidate(sent) == []


def test_past_interviews_send_nothing(client, user, application_id, sent):
    interview_id = _schedule(client, user, application_id, when=NOW - timedelta(days=1))
    _patch(client, user, interview_id, status="cancelled")
    assert _to_candidate(sent) == []


def test_switch_off_sends_nothing(client, user, application_id, sent):
    with SessionLocal() as db:
        db.query(TelegramLink).filter_by(kind=TelegramAccountKind.CANDIDATE).one().notify_reminders = False
        db.commit()
    _schedule(client, user, application_id)
    assert _to_candidate(sent) == []


def test_hr_is_not_told_about_their_own_change(client, user, application_id, sent):
    _link_hr(user["id"])
    _schedule(client, user, application_id)
    assert [message["chat_id"] for message in sent] == [TG_USER]


def test_telegram_off_queues_nothing(client, user, application_id, monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_ENABLED", False)
    _schedule(client, user, application_id)
    with SessionLocal() as db:
        assert db.query(OutboxEvent).filter(OutboxEvent.event_type == notifier.EVENT_TYPE).count() == 0


def test_stale_messages_are_dropped(client, user, application_id, sent):
    interview_id = _schedule(client, user, application_id)
    payload = {
        "notification": notifier.INTERVIEW_UPDATE,
        "change": notifier.CHANGE_SCHEDULED,
        "interview_id": interview_id,
        "application_id": application_id,
        "scheduled_at": SLOT_UTC.isoformat(),
    }
    with SessionLocal() as db:
        assert notifier.build_message(db, payload) is not None
    # Moved since it was queued: the "scheduled" message for the old time is stale.
    _patch(client, user, interview_id, scheduled_at=NEW_SLOT_UTC.isoformat())
    with SessionLocal() as db:
        assert notifier.build_message(db, payload) is None
        # A cancellation that was undone since is not sent either.
        cancelled = dict(payload, change=notifier.CHANGE_CANCELLED, scheduled_at=NEW_SLOT_UTC.isoformat())
        assert notifier.build_message(db, cancelled) is None


def test_candidate_settings_name_the_switch(client, application_id):
    reply = actions.settings_page(_candidate_profile())
    assert "Suhbatlar: o'zgarishlar va eslatmalar" in reply.text


# --- HR: reschedule and cancel from the bot ----------------------------------------


@pytest.fixture
def hr(user, application_id):
    _link_hr(user["id"])
    return user


@pytest.fixture
def interview_id(client, hr, application_id, sent):
    interview_id = _schedule(client, hr, application_id)
    sent.clear()
    return interview_id


def _callbacks(reply):
    return [button["callback_data"] for row in reply.buttons for button in row if "callback_data" in button]


def test_card_offers_reschedule_and_cancel(application_id, interview_id):
    reply = actions.hr_application_detail(_hr_profile(), application_id, page=2)
    callbacks = _callbacks(reply)
    assert f"hr:rs:{interview_id}:2" in callbacks and f"hr:ivx:{interview_id}:2" in callbacks


def test_card_without_interview_has_no_manage_buttons(hr, application_id):
    callbacks = _callbacks(actions.hr_application_detail(_hr_profile(), application_id))
    assert not any(c.startswith(("hr:rs:", "hr:ivx:")) for c in callbacks)


def test_reschedule_pickers_use_their_own_callbacks(application_id, interview_id):
    days = actions.hr_reschedule_days(_hr_profile(), interview_id)
    assert "Hozirgi vaqt: 02.12.2026 14:00" in days.text
    assert f"hr:rsd:{interview_id}:20261203:0" in _callbacks(days)

    times = actions.hr_reschedule_times(_hr_profile(), interview_id, "20261203")
    # The picker keeps the interview's 45 minutes.
    assert f"hr:rst:{interview_id}:{NEW_SLOT}:45:0" in _callbacks(times)

    review = actions.hr_reschedule_review(_hr_profile(), interview_id, NEW_SLOT, 45)
    assert f"hr:rsok:{interview_id}:{NEW_SLOT}:45:0" in _callbacks(review)
    assert "Alice HR" in review.text


def test_reschedule_moves_audits_and_tells_the_candidate(application_id, interview_id, sent):
    reply = actions.hr_reschedule_confirm(_hr_profile(), interview_id, NEW_SLOT, 60, page=1)

    assert "vaqti o'zgartirildi" in reply.text and "03.12.2026 11:30" in reply.text
    with SessionLocal() as db:
        interview = db.get(Interview, interview_id)
        assert notifier._as_utc(interview.scheduled_at) == NEW_SLOT_UTC
        assert interview.duration_minutes == 60
        entry = (
            db.query(AuditLog)
            .filter(AuditLog.action == "UPDATE_INTERVIEW", AuditLog.resource_id == str(interview_id))
            .one()
        )
        assert entry.details == {"fields": ["duration_minutes", "scheduled_at"], "via": "telegram"}
    [message] = _to_candidate(sent)
    assert "vaqti o'zgardi" in message["text"]

    # A second tap changes nothing.
    actions.hr_reschedule_confirm(_hr_profile(), interview_id, NEW_SLOT, 60, page=1)
    with SessionLocal() as db:
        assert db.query(AuditLog).filter(AuditLog.action == "UPDATE_INTERVIEW").count() == 1
    assert len(_to_candidate(sent)) == 1


def test_reschedule_to_a_past_slot_goes_back_to_the_days(interview_id):
    reply = actions.hr_reschedule_confirm(_hr_profile(), interview_id, "202612010900", 60)
    assert "endi mavjud emas" in reply.text
    assert any(c.startswith(f"hr:rsd:{interview_id}:") for c in _callbacks(reply))


def test_cancel_asks_first_then_cancels(application_id, interview_id, sent):
    ask = actions.hr_cancel_interview(_hr_profile(), interview_id, page=1)
    assert "bekor qilasizmi" in ask.text
    assert _callbacks(ask) == [f"hr:ivxok:{interview_id}:1", f"hr:app:{application_id}:1"]
    with SessionLocal() as db:
        assert db.get(Interview, interview_id).status == InterviewStatus.UPCOMING

    done = actions.hr_cancel_interview(_hr_profile(), interview_id, page=1, confirmed=True)
    assert "Suhbat bekor qilindi" in done.text
    assert not any(c.startswith("hr:ivx:") for c in _callbacks(done))
    with SessionLocal() as db:
        assert db.get(Interview, interview_id).status == InterviewStatus.CANCELLED
        entry = db.query(AuditLog).filter(AuditLog.action == "UPDATE_INTERVIEW").one()
        assert entry.details["status"] == "cancelled" and entry.details["via"] == "telegram"
    [message] = _to_candidate(sent)
    assert "bekor qilindi" in message["text"]

    # Tapping the old confirmation again finds nothing to cancel.
    again = actions.hr_cancel_interview(_hr_profile(), interview_id, confirmed=True)
    assert "topilmadi" in again.text
    assert len(_to_candidate(sent)) == 1


def test_other_hr_cannot_touch_the_interview(other_user, interview_id):
    _link_hr(other_user["id"], telegram_user_id=OTHER_TG)
    profile = _hr_profile(OTHER_TG)
    assert "topilmadi" in actions.hr_reschedule_days(profile, interview_id).text
    assert "topilmadi" in actions.hr_reschedule_confirm(profile, interview_id, NEW_SLOT, 60).text
    assert "topilmadi" in actions.hr_cancel_interview(profile, interview_id, confirmed=True).text
    with SessionLocal() as db:
        interview = db.get(Interview, interview_id)
        assert interview.status == InterviewStatus.UPCOMING
        assert notifier._as_utc(interview.scheduled_at) == SLOT_UTC


def test_texts_exist_in_every_language(application_id, interview_id):
    for lang, word in (("ru", "Перенести"), ("en", "Reschedule")):
        reply = actions.hr_application_detail(_hr_profile(HR_TG, language_code=lang), application_id)
        assert word in str(reply.buttons)
