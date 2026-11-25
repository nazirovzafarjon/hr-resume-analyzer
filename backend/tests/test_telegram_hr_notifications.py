"""Telegram bot phase 3: HR new-application notifications and /new."""

import json

import pytest

from app.bot import actions
from app.core.config import settings
from app.core.database import SessionLocal
from app.crud import application as application_crud
from app.models.application import AnalysisStatus, Application, ApplicationStatus
from app.models.outbox import OutboxEvent
from app.models.telegram_link import TelegramAccountKind, TelegramLink
from app.models.user import User
from app.schemas.application import ApplicationCreate
from app.services.telegram import client as tg_client
from app.services.telegram import notifier
from app.services.telegram.linking import TelegramProfile
from tests.payloads import APPLICATION_PAYLOAD, JOB_PAYLOAD

HR_TG = 888_000_111
OTHER_TG = 888_000_222

FORM_FIELDS = [
    {"label": "Full name", "type": "text", "required": True},
    {"label": "Email", "type": "email", "required": True},
    {"label": "Resume", "type": "file", "required": True},
]


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


def _link_hr(user_id, telegram_user_id=HR_TG, language="uz"):
    with SessionLocal() as db:
        db.add(
            TelegramLink(
                kind=TelegramAccountKind.HR,
                user_id=user_id,
                telegram_user_id=telegram_user_id,
                chat_id=telegram_user_id,
                language=language,
            )
        )
        db.commit()


def _create_job(client, headers, **overrides):
    payload = dict(JOB_PAYLOAD, application_form={"fields": FORM_FIELDS}, **overrides)
    response = client.post("/api/jobs", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def job(client, user):
    return _create_job(client, user["headers"])


def _submit_form(client, job, name="Jane Doe", email="jane@example.com"):
    """Apply through the public application form (the main intake path)."""
    form = job["application_form"]
    name_id, email_id, resume_id = [f["id"] for f in form["fields"]]
    response = client.post(
        f"/api/public/applications/{form['public_token']}/submit",
        files={
            "values": (None, json.dumps({name_id: name, email_id: email, resume_id: ""})),
            resume_id: ("cv.pdf", b"%PDF-fake", "application/pdf"),
        },
    )
    assert response.status_code == 201, response.text


def _add_application(job_id, *, name="Jane Doe", status=ApplicationStatus.NEW, **fields):
    """Insert an application directly (no notifications involved)."""
    with SessionLocal() as db:
        application = Application(
            job_id=job_id,
            name=name,
            email="jane@example.com",
            resume_path="",
            application_status=status,
            **fields,
        )
        db.add(application)
        db.commit()
        return application.id


def _telegram_events():
    with SessionLocal() as db:
        return db.query(OutboxEvent).filter(OutboxEvent.event_type == notifier.EVENT_TYPE).count()


def _profile(telegram_user_id=HR_TG, language_code="uz"):
    return TelegramProfile(telegram_user_id=telegram_user_id, chat_id=telegram_user_id, language_code=language_code)


# --- notifications -------------------------------------------------------------


def test_form_submission_notifies_job_owner(client, user, telegram_on, sent, job):
    _link_hr(user["id"])
    _submit_form(client, job)

    assert len(sent) == 1
    message = sent[0]
    assert message["chat_id"] == HR_TG
    assert "Yangi ariza" in message["text"]
    assert "Jane Doe" in message["text"] and JOB_PAYLOAD["position"] in message["text"]
    callback = message["buttons"][0][0]["callback_data"]
    assert callback.startswith("hr:app:") and callback.endswith(":0")


def test_legacy_public_apply_notifies_job_owner(client, user, telegram_on, sent, job):
    _link_hr(user["id"])
    response = client.post(
        f"/api/public/apply/{job['public_id']}",
        data={"name": "Anon", "email": "anon@example.com"},
        files={"resume": ("cv.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 201, response.text
    assert len(sent) == 1 and "Anon" in sent[0]["text"]


def test_hr_entered_application_is_not_announced(client, user, telegram_on, sent, job):
    _link_hr(user["id"])
    response = client.post(
        f"/api/applications?job_id={job['id']}", json=APPLICATION_PAYLOAD, headers=user["headers"]
    )
    assert response.status_code == 201, response.text
    assert sent == []


def test_only_the_job_owner_is_notified(client, user, other_user, telegram_on, sent, job):
    _link_hr(other_user["id"], telegram_user_id=OTHER_TG)
    _submit_form(client, job)
    assert sent == []
    assert _telegram_events() == 0


def test_nothing_queued_without_hr_link(client, user, telegram_on, sent, job):
    _submit_form(client, job)
    assert sent == [] and _telegram_events() == 0


def test_nothing_queued_when_bot_disabled(client, user, sent, job):
    _link_hr(user["id"])
    _submit_form(client, job)
    assert sent == [] and _telegram_events() == 0


def test_candidate_and_hr_are_both_notified(client, user, telegram_on, sent, job):
    from tests.test_telegram_notifications import _link, _register_candidate

    candidate_id = _register_candidate(client, "jane@example.com")
    _link(candidate_id, telegram_user_id=555_000_001)
    _link_hr(user["id"])
    with SessionLocal() as db:
        application_crud.create_application(
            db,
            job["id"],
            ApplicationCreate(**APPLICATION_PAYLOAD),
            candidate_account_id=candidate_id,
            notify_owner=True,
        )
    assert sorted(m["chat_id"] for m in sent) == sorted([555_000_001, HR_TG])


def test_deactivated_hr_is_skipped_at_send_time(client, user, telegram_on, job):
    _link_hr(user["id"])
    application_id = _add_application(job["id"])
    with SessionLocal() as db:
        db.get(User, user["id"]).is_active = False
        db.commit()
        payload = {"notification": notifier.NEW_APPLICATION, "application_id": application_id}
        assert notifier.build_message(db, payload) is None


def test_applicant_name_is_html_escaped(client, user, telegram_on, sent, job):
    _link_hr(user["id"])
    _submit_form(client, job, name="<b>Eve</b> & Co")
    assert "&lt;b&gt;Eve&lt;/b&gt; &amp; Co" in sent[0]["text"]


def test_message_language_follows_the_link(client, user, telegram_on, sent, job):
    _link_hr(user["id"], language="ru")
    _submit_form(client, job)
    assert "Новая заявка" in sent[0]["text"]


def test_crm_url_skips_local_hosts(monkeypatch):
    monkeypatch.setattr(settings, "FRONTEND_BASE_URL", "http://localhost:5173")
    assert notifier.crm_url(5) is None
    monkeypatch.setattr(settings, "FRONTEND_BASE_URL", "https://hr.example.com/")
    assert notifier.crm_url(5) == "https://hr.example.com/applications/5"
    buttons = notifier.hr_application_buttons("en", 5)
    assert buttons[1][0]["url"] == "https://hr.example.com/applications/5"


# --- /new ------------------------------------------------------------------------


def test_new_requires_hr_link(telegram_on):
    assert "HR uchun" in actions.hr_new_page(_profile()).text


def test_new_empty(telegram_on, user):
    _link_hr(user["id"])
    assert "yo'q" in actions.hr_new_page(_profile()).text


def test_new_lists_only_own_unreviewed_applications(client, user, other_user, telegram_on, job):
    _link_hr(user["id"])
    for number in range(6):
        _add_application(job["id"], name=f"Applicant {number}")
    _add_application(job["id"], name="Already reviewing", status=ApplicationStatus.REVIEWING)
    foreign_job = _create_job(client, other_user["headers"])
    _add_application(foreign_job["id"], name="Someone else's")

    first = actions.hr_new_page(_profile())
    assert "(6 ta) — 1/2" in first.text
    assert "Already reviewing" not in first.text and "Someone else's" not in first.text
    assert len([row for row in first.buttons if row[0]["callback_data"].startswith("hr:app:")]) == 5
    assert first.buttons[-1][0]["callback_data"] == "hr:new:1"

    second = actions.hr_new_page(_profile(), page=1)
    assert "2/2" in second.text
    assert second.buttons[-1][0]["callback_data"] == "hr:new:0"


def test_hr_detail_shows_applicant_and_status(telegram_on, user, job):
    _link_hr(user["id"])
    application_id = _add_application(job["id"], status=ApplicationStatus.SHORTLISTED)

    reply = actions.hr_application_detail(_profile(), application_id, page=0)
    assert "Jane Doe" in reply.text and "jane@example.com" in reply.text
    assert "Tanlangan" in reply.text
    assert "AI tahlili hali o'tkazilmagan" in reply.text
    assert reply.buttons[-1][0]["callback_data"] == "hr:new:0"


def test_hr_detail_shows_ai_score(telegram_on, user, job):
    _link_hr(user["id"], language="en")
    application_id = _add_application(
        job["id"], analysis_status=AnalysisStatus.COMPLETED, ai_score=82.4
    )
    reply = actions.hr_application_detail(_profile(language_code="en"), application_id)
    assert "AI match: <b>82%</b>" in reply.text


def test_hr_detail_is_scoped_to_own_jobs(client, user, other_user, telegram_on):
    _link_hr(user["id"])
    foreign_job = _create_job(client, other_user["headers"])
    application_id = _add_application(foreign_job["id"])

    reply = actions.hr_application_detail(_profile(), application_id)
    assert "topilmadi" in reply.text
