"""Telegram bot phase 4: HR changes an application's status from the bot."""

import pytest

from app.bot import actions
from app.core.database import SessionLocal
from app.models.application import Application, ApplicationStatus
from app.models.application_status_history import ApplicationStatusHistory
from app.models.audit_log import AuditLog
from app.core.config import settings
from app.services.telegram import client as tg_client
from tests.test_telegram_hr_notifications import (
    _add_application,
    _create_job,
    _link_hr,
    _profile,
)
from tests.test_telegram_notifications import _link, _register_candidate

CANDIDATE_TG = 555_000_009


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
def job(client, user):
    return _create_job(client, user["headers"])


def _status(application_id):
    with SessionLocal() as db:
        return db.get(Application, application_id).application_status


def _callbacks(reply):
    return [button["callback_data"] for row in reply.buttons for button in row if "callback_data" in button]


@pytest.fixture
def hr(user, telegram_on):
    _link_hr(user["id"])
    return user


def test_card_offers_every_other_status(hr, job):
    application_id = _add_application(job["id"])
    reply = actions.hr_application_detail(_profile(), application_id, page=1)
    callbacks = _callbacks(reply)
    for status in ("reviewing", "shortlisted", "interview", "hired", "rejected"):
        assert f"hr:set:{application_id}:{status}:1" in callbacks
    assert "Ko'rib chiqishni boshlash" in str(reply.buttons) and "Rad etish" in str(reply.buttons)
    assert callbacks[-1] == "hr:back:1"


def test_card_hides_the_current_status(hr, job):
    application_id = _add_application(job["id"], status=ApplicationStatus.INTERVIEW)
    callbacks = _callbacks(actions.hr_application_detail(_profile(), application_id))
    assert f"hr:set:{application_id}:interview:0" not in callbacks
    assert f"hr:set:{application_id}:hired:0" in callbacks


def test_withdrawn_application_has_no_actions(hr, job):
    application_id = _add_application(job["id"], status=ApplicationStatus.WITHDRAWN)
    callbacks = _callbacks(actions.hr_application_detail(_profile(), application_id))
    assert not any(c.startswith("hr:set:") for c in callbacks)
    reply = actions.hr_set_status(_profile(), application_id, "reviewing")
    assert _status(application_id) == ApplicationStatus.WITHDRAWN
    assert "Qaytarib olingan" in reply.text


def test_set_status_updates_history_and_audit(hr, job):
    application_id = _add_application(job["id"])

    reply = actions.hr_set_status(_profile(), application_id, "shortlisted", page=0)

    assert _status(application_id) == ApplicationStatus.SHORTLISTED
    assert "Holat o'zgartirildi: <b>Tanlangan</b>" in reply.text
    with SessionLocal() as db:
        history = [
            h.status
            for h in db.query(ApplicationStatusHistory).filter_by(application_id=application_id)
        ]
        assert "shortlisted" in history
        entry = (
            db.query(AuditLog)
            .filter(AuditLog.action == "UPDATE_APPLICATION", AuditLog.resource_id == str(application_id))
            .one()
        )
        assert entry.actor_user_id == hr["id"]
        assert entry.details["application_status"] == "shortlisted"
        assert entry.details["via"] == "telegram"


def test_status_change_notifies_the_candidate(client, hr, sent, job):
    candidate_id = _register_candidate(client, "cand@example.com")
    _link(candidate_id, telegram_user_id=CANDIDATE_TG)
    application_id = _add_application(job["id"], candidate_account_id=candidate_id)

    actions.hr_set_status(_profile(), application_id, "interview")

    to_candidate = [m for m in sent if m["chat_id"] == CANDIDATE_TG]
    assert len(to_candidate) == 1 and "Suhbatga taklif" in to_candidate[0]["text"]


@pytest.mark.parametrize("target", ["rejected", "hired"])
def test_final_decisions_ask_for_confirmation(hr, job, target):
    application_id = _add_application(job["id"])

    confirm = actions.hr_set_status(_profile(), application_id, target, page=2)
    assert _status(application_id) == ApplicationStatus.NEW
    assert "tasdiqlayman" in str(confirm.buttons)
    assert _callbacks(confirm) == [f"hr:ok:{application_id}:{target}:2", f"hr:app:{application_id}:2"]

    done = actions.hr_set_status(_profile(), application_id, target, page=2, confirmed=True)
    assert _status(application_id) == ApplicationStatus(target)
    assert "✅" in done.text


def test_repeated_tap_changes_nothing(hr, job):
    application_id = _add_application(job["id"], status=ApplicationStatus.REVIEWING)
    reply = actions.hr_set_status(_profile(), application_id, "reviewing")
    assert "o'zgartirildi" not in reply.text
    with SessionLocal() as db:
        assert db.query(AuditLog).filter(AuditLog.action == "UPDATE_APPLICATION").count() == 0


@pytest.mark.parametrize("target", ["new", "withdrawn", "bogus"])
def test_only_hr_targets_are_accepted(hr, job, target):
    application_id = _add_application(job["id"], status=ApplicationStatus.REVIEWING)
    reply = actions.hr_set_status(_profile(), application_id, target)
    assert _status(application_id) == ApplicationStatus.REVIEWING
    assert "Xatolik" in reply.text


def test_cannot_change_another_owners_application(client, hr, other_user):
    foreign_job = _create_job(client, other_user["headers"])
    application_id = _add_application(foreign_job["id"])
    reply = actions.hr_set_status(_profile(), application_id, "rejected", confirmed=True)
    assert _status(application_id) == ApplicationStatus.NEW
    assert "topilmadi" in reply.text


def test_requires_an_hr_link(telegram_on, user, job):
    application_id = _add_application(job["id"])
    reply = actions.hr_set_status(_profile(), application_id, "reviewing")
    assert "HR uchun" in reply.text
    assert _status(application_id) == ApplicationStatus.NEW


def test_unverified_or_inactive_hr_cannot_act(hr, job):
    from app.models.user import User

    application_id = _add_application(job["id"])
    with SessionLocal() as db:
        db.get(User, hr["id"]).is_active = False
        db.commit()
    reply = actions.hr_set_status(_profile(), application_id, "reviewing")
    assert "HR uchun" in reply.text
    assert _status(application_id) == ApplicationStatus.NEW


def test_callback_data_fits_telegram_limit():
    longest = f"hr:set:{10**9}:shortlisted:{999}"
    assert len(longest.encode()) <= 64
