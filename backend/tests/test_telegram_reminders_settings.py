"""Telegram bot phase 5: interview reminders, /settings and webhook config."""

from datetime import datetime, timedelta, timezone

import pytest

from app.bot import actions
from app.bot.__main__ import webhook_config_error, webhook_path
from app.core.config import settings
from app.core.database import SessionLocal
from app.crud import application as application_crud
from app.models.interview import Interview, InterviewStatus
from app.models.telegram_link import TelegramAccountKind, TelegramInterviewReminder, TelegramLink
from app.schemas.application import ApplicationCreate
from app.services.telegram import client as tg_client
from app.services.telegram import notifier
from tests.payloads import APPLICATION_PAYLOAD
from tests.test_telegram_hr_notifications import (
    HR_TG,
    _add_application,
    _create_job,
    _link_hr,
    _profile,
)
from tests.test_telegram_notifications import _link, _register_candidate

CANDIDATE_TG = 555_000_123
NOW = datetime(2026, 12, 1, 9, 0, tzinfo=timezone.utc)


@pytest.fixture
def telegram_on(monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_ENABLED", True)
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "123:test-token")
    monkeypatch.setattr(settings, "TELEGRAM_BOT_USERNAME", "ra_test_bot")


@pytest.fixture
def sent(monkeypatch):
    """Capture outgoing Bot API messages instead of calling Telegram."""
    messages: list[dict] = []

    def fake_send(chat_id, text, *, buttons=None):
        messages.append({"chat_id": chat_id, "text": text, "buttons": buttons or []})
        return {"message_id": len(messages)}

    monkeypatch.setattr(tg_client, "send_message", fake_send)
    return messages


@pytest.fixture
def frozen_now(monkeypatch):
    """Send-time checks ("is the interview still ahead?") use the test clock."""
    monkeypatch.setattr(notifier, "_utcnow", lambda: NOW)
    return NOW


@pytest.fixture
def job(client, user):
    return _create_job(client, user["headers"])


@pytest.fixture
def setup(client, user, telegram_on, job):
    """A candidate application to the HR's job, both sides linked."""
    candidate_id = _register_candidate(client, "cand@example.com")
    _link(candidate_id, telegram_user_id=CANDIDATE_TG)
    _link_hr(user["id"])
    application_id = _add_application(job["id"], candidate_account_id=candidate_id)
    return {"user": user, "candidate_id": candidate_id, "application_id": application_id}


def _interview(application_id, hr_id, *, ahead, status=InterviewStatus.UPCOMING, meeting_link=None):
    with SessionLocal() as db:
        interview = Interview(
            candidate_id=application_id,
            hr_id=hr_id,
            interviewer="Ali",
            scheduled_at=NOW + ahead,
            status=status,
            meeting_link=meeting_link,
        )
        db.add(interview)
        db.commit()
        return interview.id


def _scan(now=NOW):
    with SessionLocal() as db:
        events = notifier.scan_interview_reminders(db, now=now)
        for event in events:
            notifier.publish(db, event)
        return len(events)


def _set_pref(kind, column, value):
    with SessionLocal() as db:
        db.query(TelegramLink).filter(TelegramLink.kind == kind).update({column: value})
        db.commit()


# --- interview reminders -------------------------------------------------------


def test_day_reminder_goes_to_candidate_and_hr(setup, sent, frozen_now):
    _interview(setup["application_id"], setup["user"]["id"], ahead=timedelta(hours=20))

    assert _scan() == 2
    by_chat = {m["chat_id"]: m for m in sent}
    candidate, hr = by_chat[CANDIDATE_TG], by_chat[HR_TG]
    assert "Suhbat eslatmasi" in candidate["text"] and "24 soatdan kam" in candidate["text"]
    assert "Jane Doe" not in candidate["text"]
    assert "Jane Doe" in hr["text"]
    assert candidate["buttons"][0][0]["callback_data"] == f"app:{setup['application_id']}:0"
    assert hr["buttons"][0][0]["callback_data"] == f"hr:app:{setup['application_id']}:0"
    # 09:00 UTC + 20h = 05:00 UTC next day = 10:00 in Tashkent.
    assert "02.12.2026 10:00" in candidate["text"]


def test_each_window_is_sent_once(setup, sent, frozen_now):
    _interview(setup["application_id"], setup["user"]["id"], ahead=timedelta(hours=20))
    assert _scan() == 2
    assert _scan(NOW + timedelta(minutes=5)) == 0
    assert len(sent) == 2


def test_hour_reminder_follows_the_day_one(setup, sent, frozen_now):
    _interview(setup["application_id"], setup["user"]["id"], ahead=timedelta(hours=20))
    _scan()
    sent.clear()

    later = NOW + timedelta(hours=19, minutes=10)  # 50 minutes before
    with SessionLocal() as db:
        windows = [e.payload["window"] for e in notifier.scan_interview_reminders(db, now=later)]
    assert windows == ["1h", "1h"]


def test_late_interview_only_gets_the_hour_reminder(setup, sent, frozen_now):
    interview_id = _interview(setup["application_id"], setup["user"]["id"], ahead=timedelta(minutes=30))
    assert _scan() == 2
    assert all("1 soatdan keyin" in m["text"] for m in sent)
    with SessionLocal() as db:
        windows = {
            r.reminder_window
            for r in db.query(TelegramInterviewReminder).filter_by(interview_id=interview_id)
        }
    assert windows == {"1h"}


@pytest.mark.parametrize(
    "ahead,status",
    [
        (timedelta(hours=30), InterviewStatus.UPCOMING),
        (timedelta(hours=-1), InterviewStatus.UPCOMING),
        (timedelta(hours=2), InterviewStatus.CANCELLED),
        (timedelta(hours=2), InterviewStatus.COMPLETED),
    ],
)
def test_no_reminder_outside_the_window_or_when_not_upcoming(setup, sent, frozen_now, ahead, status):
    _interview(setup["application_id"], setup["user"]["id"], ahead=ahead, status=status)
    assert _scan() == 0 and sent == []


def test_rescheduling_arms_the_reminder_again(setup, sent, frozen_now):
    interview_id = _interview(setup["application_id"], setup["user"]["id"], ahead=timedelta(hours=20))
    _scan()
    with SessionLocal() as db:
        db.get(Interview, interview_id).scheduled_at = NOW + timedelta(hours=22)
        db.commit()
    sent.clear()
    assert _scan(NOW + timedelta(minutes=5)) == 2
    assert len(sent) == 2


def test_stale_reminder_is_dropped_at_send_time(setup, frozen_now, telegram_on):
    interview_id = _interview(setup["application_id"], setup["user"]["id"], ahead=timedelta(hours=20))
    with SessionLocal() as db:
        events = notifier.scan_interview_reminders(db, now=NOW)
        payload = events[0].payload
        db.get(Interview, interview_id).status = InterviewStatus.CANCELLED
        db.commit()
        assert notifier.build_message(db, payload) is None


def test_moved_interview_drops_the_old_reminder(setup, frozen_now):
    interview_id = _interview(setup["application_id"], setup["user"]["id"], ahead=timedelta(hours=20))
    with SessionLocal() as db:
        payload = notifier.scan_interview_reminders(db, now=NOW)[0].payload
        db.get(Interview, interview_id).scheduled_at = NOW + timedelta(hours=5)
        db.commit()
        assert notifier.build_message(db, payload) is None


def test_meeting_link_is_shown_only_for_web_links(setup, sent, frozen_now):
    _interview(
        setup["application_id"],
        setup["user"]["id"],
        ahead=timedelta(hours=3),
        meeting_link="https://meet.example.com/abc?x=1&y=<2>",
    )
    _scan()
    assert "🔗 https://meet.example.com/abc?x=1&amp;y=&lt;2&gt;" in sent[0]["text"]
    assert notifier._meeting_line("javascript:alert(1)") is None
    assert notifier._meeting_line("Room 4") is None


def test_reminders_switch_is_respected(setup, sent, frozen_now):
    _set_pref(TelegramAccountKind.CANDIDATE, TelegramLink.notify_reminders, False)
    _interview(setup["application_id"], setup["user"]["id"], ahead=timedelta(hours=3))
    assert _scan() == 1
    assert [m["chat_id"] for m in sent] == [HR_TG]


def test_scan_is_a_no_op_when_the_bot_is_off(client, user, job, sent):
    application_id = _add_application(job["id"])
    _interview(application_id, user["id"], ahead=timedelta(hours=3))
    with SessionLocal() as db:
        assert notifier.scan_interview_reminders(db, now=NOW) == []
        assert db.query(TelegramInterviewReminder).count() == 0


# --- preferences in the other notifications ------------------------------------


def test_status_switch_silences_status_changes(client, setup, sent):
    _set_pref(TelegramAccountKind.CANDIDATE, TelegramLink.notify_status, False)
    response = client.patch(
        f"/api/applications/{setup['application_id']}",
        json={"application_status": "reviewing"},
        headers=setup["user"]["headers"],
    )
    assert response.status_code == 200
    assert [m for m in sent if m["chat_id"] == CANDIDATE_TG] == []


def test_new_applications_switch_silences_hr(user, telegram_on, sent, job):
    _link_hr(user["id"])
    _set_pref(TelegramAccountKind.HR, TelegramLink.notify_new_applications, False)
    with SessionLocal() as db:
        application_crud.create_application(
            db, job["id"], ApplicationCreate(**APPLICATION_PAYLOAD), notify_owner=True
        )
    assert sent == []


# --- /settings ---------------------------------------------------------------


def test_settings_requires_a_link(telegram_on):
    assert "/start" in actions.settings_page(_profile()).text


def test_settings_lists_switches_per_account(setup):
    # Only the HR link belongs to this Telegram user here.
    reply = actions.settings_page(_profile())
    callbacks = [row[0]["callback_data"] for row in reply.buttons]
    assert callbacks == ["cfg:hr:new_applications", "cfg:hr:reminders"]
    assert "✅ Yangi arizalar" in reply.text and "✅ Suhbat eslatmalari" in reply.text


def test_settings_with_both_accounts_marks_each_button(client, user, telegram_on):
    candidate_id = _register_candidate(client, "both@example.com")
    _link_hr(user["id"])
    _link(candidate_id, telegram_user_id=HR_TG)
    reply = actions.settings_page(_profile())
    callbacks = [row[0]["callback_data"] for row in reply.buttons]
    assert callbacks == [
        "cfg:hr:new_applications",
        "cfg:hr:reminders",
        "cfg:candidate:status",
        "cfg:candidate:reminders",
    ]
    assert reply.buttons[0][0]["text"].endswith("· HR")
    assert "<b>Nomzod</b>" in reply.text


def test_toggle_flips_and_persists(setup):
    reply = actions.toggle_setting(_profile(), "hr", "reminders")
    assert "🔕 Suhbat eslatmalari" in reply.text
    with SessionLocal() as db:
        assert db.query(TelegramLink).filter_by(kind=TelegramAccountKind.HR).one().notify_reminders is False
    reply = actions.toggle_setting(_profile(), "hr", "reminders")
    assert "✅ Suhbat eslatmalari" in reply.text


@pytest.mark.parametrize(
    "kind,key", [("hr", "status"), ("candidate", "new_applications"), ("admin", "reminders"), ("hr", "x")]
)
def test_toggle_rejects_unknown_switches(setup, kind, key):
    assert "Xatolik" in actions.toggle_setting(_profile(), kind, key).text


def test_toggle_only_touches_own_links(setup):
    # The candidate link belongs to another Telegram user: nothing changes for it.
    actions.toggle_setting(_profile(), "candidate", "status")
    with SessionLocal() as db:
        assert db.query(TelegramLink).filter_by(kind=TelegramAccountKind.CANDIDATE).one().notify_status is True


# --- webhook configuration -------------------------------------------------------


def test_webhook_config_validation(monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_WEBHOOK_URL", "")
    assert webhook_config_error() is None

    monkeypatch.setattr(settings, "TELEGRAM_WEBHOOK_URL", "http://hr.example.com/telegram/webhook")
    monkeypatch.setattr(settings, "TELEGRAM_WEBHOOK_SECRET", "s3cret_value")
    assert "https" in webhook_config_error()

    monkeypatch.setattr(settings, "TELEGRAM_WEBHOOK_URL", "https://hr.example.com/telegram/webhook")
    monkeypatch.setattr(settings, "TELEGRAM_WEBHOOK_SECRET", "")
    assert "SECRET" in webhook_config_error()
    monkeypatch.setattr(settings, "TELEGRAM_WEBHOOK_SECRET", "bad secret!")
    assert "SECRET" in webhook_config_error()

    monkeypatch.setattr(settings, "TELEGRAM_WEBHOOK_SECRET", "s3cret_value-123")
    assert webhook_config_error() is None
    assert webhook_path() == "/telegram/webhook"


def test_reminder_task_runs_the_scan(setup, sent, monkeypatch):
    from app.tasks.notifications import send_interview_reminders_task

    monkeypatch.setattr(notifier, "_utcnow", lambda: datetime.now(timezone.utc))
    with SessionLocal() as db:
        db.add(
            Interview(
                candidate_id=setup["application_id"],
                hr_id=setup["user"]["id"],
                interviewer="Ali",
                scheduled_at=datetime.now(timezone.utc) + timedelta(hours=2),
            )
        )
        db.commit()
    assert send_interview_reminders_task() == {"queued": 2}
    assert len(sent) == 2
