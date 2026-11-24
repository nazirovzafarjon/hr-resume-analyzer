"""Telegram bot phase 2: candidate status notifications and /applications."""

from datetime import datetime, timezone

import httpx
import pytest

from app.bot import actions
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import create_candidate_email_verification_token
from app.crud import application as application_crud
from app.models.outbox import OutboxEvent, OutboxStatus
from app.models.telegram_link import TelegramAccountKind, TelegramLink
from app.schemas.application import ApplicationCreate
from app.services.telegram import client as tg_client
from app.services.telegram import notifier
from app.services.telegram.linking import TelegramProfile
from tests.payloads import APPLICATION_PAYLOAD, JOB_PAYLOAD

TG_USER = 777_000_222


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


def _register_candidate(client, email):
    response = client.post(
        "/api/candidate/auth/register",
        json={"email": email, "full_name": "Jane", "password": "CandidatePass1"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    client.post(
        "/api/candidate/auth/verify-email",
        json={"token": create_candidate_email_verification_token(body["candidate"]["id"])},
    )
    return body["candidate"]["id"]


def _link(candidate_id, telegram_user_id=TG_USER, language="uz"):
    with SessionLocal() as db:
        db.add(
            TelegramLink(
                kind=TelegramAccountKind.CANDIDATE,
                candidate_account_id=candidate_id,
                telegram_user_id=telegram_user_id,
                chat_id=telegram_user_id,
                language=language,
            )
        )
        db.commit()


@pytest.fixture
def candidate_id(client):
    return _register_candidate(client, "jane@example.com")


@pytest.fixture
def job(client, user):
    response = client.post("/api/jobs", json=JOB_PAYLOAD, headers=user["headers"])
    assert response.status_code == 201, response.text
    return response.json()


def _apply(job_id, candidate_id):
    """Create an application submitted by the candidate account."""
    with SessionLocal() as db:
        application = application_crud.create_application(
            db, job_id, ApplicationCreate(**APPLICATION_PAYLOAD), candidate_account_id=candidate_id
        )
        return application.id


def _set_status(client, user, application_id, status):
    response = client.patch(
        f"/api/applications/{application_id}",
        json={"application_status": status},
        headers=user["headers"],
    )
    assert response.status_code == 200, response.text
    return response


def _profile(telegram_user_id=TG_USER, language_code="uz"):
    return TelegramProfile(telegram_user_id=telegram_user_id, chat_id=telegram_user_id, language_code=language_code)


# --- notifications -------------------------------------------------------------


def test_new_application_sends_confirmation(telegram_on, sent, job, candidate_id):
    _link(candidate_id)
    application_id = _apply(job["id"], candidate_id)

    assert len(sent) == 1
    message = sent[0]
    assert message["chat_id"] == TG_USER
    assert "qabul qilindi" in message["text"] and "Backend Developer" in message["text"]
    assert message["buttons"][0][0]["callback_data"] == f"app:{application_id}:0"


def test_status_change_notifies_candidate(client, user, telegram_on, sent, job, candidate_id):
    _link(candidate_id)
    application_id = _apply(job["id"], candidate_id)
    sent.clear()

    _set_status(client, user, application_id, "reviewing")
    assert len(sent) == 1
    assert "HR ko'rib chiqmoqda" in sent[0]["text"]


def test_internal_moves_are_not_announced(client, user, telegram_on, sent, job, candidate_id):
    _link(candidate_id)
    application_id = _apply(job["id"], candidate_id)
    _set_status(client, user, application_id, "reviewing")
    sent.clear()

    # reviewing -> shortlisted looks the same to the candidate ("Under HR review").
    _set_status(client, user, application_id, "shortlisted")
    assert sent == []


def test_rejection_uses_candidate_wording(client, user, telegram_on, sent, job, candidate_id):
    _link(candidate_id, language="en")
    application_id = _apply(job["id"], candidate_id)
    sent.clear()

    _set_status(client, user, application_id, "rejected")
    text = sent[0]["text"]
    assert "Application closed" in text
    assert "rejected" not in text.lower() and "shortlist" not in text.lower()


def test_hr_only_fields_do_not_notify(client, user, telegram_on, sent, job, candidate_id):
    _link(candidate_id)
    application_id = _apply(job["id"], candidate_id)
    sent.clear()
    response = client.patch(
        f"/api/applications/{application_id}",
        json={"hiring_status": "strong_hire"},
        headers=user["headers"],
    )
    assert response.status_code == 200
    assert sent == []


def test_nothing_queued_without_link(client, user, telegram_on, sent, job, candidate_id, db_session):
    application_id = _apply(job["id"], candidate_id)
    _set_status(client, user, application_id, "interview")
    assert sent == []
    assert db_session.query(OutboxEvent).filter(OutboxEvent.event_type == "send_telegram").count() == 0


def test_nothing_queued_when_bot_disabled(client, user, sent, job, candidate_id, db_session):
    _link(candidate_id)
    application_id = _apply(job["id"], candidate_id)
    _set_status(client, user, application_id, "interview")
    assert sent == []
    assert db_session.query(OutboxEvent).filter(OutboxEvent.event_type == "send_telegram").count() == 0


def test_guest_applications_are_ignored(client, user, telegram_on, sent, job, sample_application):
    _set_status(client, user, sample_application["id"], "reviewing")
    assert sent == []


def test_blocked_bot_deactivates_link(client, user, telegram_on, monkeypatch, job, candidate_id, db_session):
    _link(candidate_id)

    def blocked(*args, **kwargs):
        raise tg_client.TelegramBlockedError("Forbidden: bot was blocked by the user")

    monkeypatch.setattr(tg_client, "send_message", blocked)
    application_id = _apply(job["id"], candidate_id)

    link = db_session.query(TelegramLink).one()
    assert link.is_active is False
    # Later changes are no longer queued for an inactive link.
    _set_status(client, user, application_id, "reviewing")
    assert db_session.query(OutboxEvent).filter(OutboxEvent.event_type == "send_telegram").count() == 1


def test_delivery_failure_never_breaks_status_update(
    client, user, telegram_on, monkeypatch, job, candidate_id, db_session
):
    _link(candidate_id)
    def down(*args, **kwargs):
        raise tg_client.TelegramTransientError("down")

    monkeypatch.setattr(tg_client, "send_message", down)
    application_id = _apply(job["id"], candidate_id)
    response = _set_status(client, user, application_id, "interview")

    assert response.json()["application_status"] == "interview"
    pending = (
        db_session.query(OutboxEvent)
        .filter(OutboxEvent.event_type == "send_telegram", OutboxEvent.status == OutboxStatus.PENDING)
        .count()
    )
    # Left pending for the outbox recovery task to retry.
    assert pending >= 1


def test_job_title_is_html_escaped(client, user, telegram_on, sent, candidate_id):
    response = client.post(
        "/api/jobs", json={**JOB_PAYLOAD, "position": "<b>Dev</b> & Ops"}, headers=user["headers"]
    )
    _link(candidate_id)
    _apply(response.json()["id"], candidate_id)
    assert "&lt;b&gt;Dev&lt;/b&gt; &amp; Ops" in sent[0]["text"]


# --- /applications -------------------------------------------------------------


def test_applications_requires_candidate_link(telegram_on):
    reply = actions.applications_page(_profile())
    assert "nomzodlar uchun" in reply.text


def test_applications_empty(telegram_on, candidate_id):
    _link(candidate_id)
    assert "Hali ariza" in actions.applications_page(_profile()).text


def test_applications_are_paginated(telegram_on, sent, job, candidate_id):
    _link(candidate_id)
    ids = [_apply(job["id"], candidate_id) for _ in range(7)]

    first = actions.applications_page(_profile(), 0)
    assert "(7 ta) — 1/2" in first.text
    assert len(first.buttons) == 6  # five cards + navigation row
    assert first.buttons[-1] == [{"text": "Keyingi ›", "callback_data": "apps:1"}]

    second = actions.applications_page(_profile(), 1)
    assert "2/2" in second.text and len(second.buttons) == 3
    assert {b[0]["callback_data"] for b in second.buttons[:2]} <= {f"app:{i}:1" for i in ids}

    # Out-of-range pages clamp instead of failing.
    assert "2/2" in actions.applications_page(_profile(), 99).text


def test_application_detail_shows_status_and_timeline(client, user, telegram_on, sent, job, candidate_id):
    _link(candidate_id)
    application_id = _apply(job["id"], candidate_id)
    _set_status(client, user, application_id, "interview")

    reply = actions.application_detail(_profile(), application_id, 0)
    assert "Backend Developer" in reply.text
    assert "Suhbatga taklif" in reply.text
    assert "✅ Ariza yuborildi" in reply.text
    assert reply.buttons[-1] == [{"text": "‹ Ro'yxatga", "callback_data": "apps:0"}]


def test_application_detail_is_scoped_to_the_candidate(client, telegram_on, sent, job, candidate_id):
    other_id = _register_candidate(client, "other@example.org")
    _link(candidate_id)
    others_application = _apply(job["id"], other_id)

    assert "topilmadi" in actions.application_detail(_profile(), others_application).text


# --- helpers -----------------------------------------------------------------


def test_portal_url_skips_local_hosts(monkeypatch):
    monkeypatch.setattr(settings, "FRONTEND_BASE_URL", "http://localhost:5173")
    assert notifier.portal_url(5) is None
    monkeypatch.setattr(settings, "FRONTEND_BASE_URL", "https://hr.example.com/")
    assert notifier.portal_url(5) == "https://hr.example.com/candidate/applications/5"


def test_dates_use_configured_timezone(monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_TIMEZONE", "Asia/Tashkent")
    value = datetime(2026, 11, 24, 20, 0, tzinfo=timezone.utc)
    assert notifier.format_date(value, with_time=True) == "25.11.2026 01:00"
    monkeypatch.setattr(settings, "TELEGRAM_TIMEZONE", "Not/AZone")
    assert notifier.format_date(value) == "24.11.2026"


@pytest.mark.parametrize(
    ("status_code", "body", "error"),
    [
        (403, {"ok": False, "description": "Forbidden: bot was blocked by the user"}, tg_client.TelegramBlockedError),
        (429, {"ok": False, "parameters": {"retry_after": 7}}, tg_client.TelegramRetryAfterError),
        (502, {"ok": False}, tg_client.TelegramTransientError),
        (400, {"ok": False, "description": "Bad Request: chat not found"}, tg_client.TelegramBadRequestError),
    ],
)
def test_client_maps_bot_api_errors(monkeypatch, telegram_on, status_code, body, error):
    monkeypatch.setattr(
        tg_client.httpx, "post", lambda *a, **k: httpx.Response(status_code, json=body)
    )
    with pytest.raises(error) as exc:
        tg_client.send_message(1, "hi")
    if error is tg_client.TelegramRetryAfterError:
        assert exc.value.retry_after == 7


def test_client_sends_html_with_keyboard(monkeypatch, telegram_on):
    captured = {}

    def fake_post(url, json, timeout):
        captured.update(url=url, json=json)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    monkeypatch.setattr(tg_client.httpx, "post", fake_post)
    tg_client.send_message(42, "<b>hi</b>", buttons=[[{"text": "x", "callback_data": "y"}]])
    assert captured["url"].endswith("/bot123:test-token/sendMessage")
    assert captured["json"]["parse_mode"] == "HTML"
    assert captured["json"]["reply_markup"] == {"inline_keyboard": [[{"text": "x", "callback_data": "y"}]]}


def test_network_error_is_transient(monkeypatch, telegram_on):
    def boom(*a, **k):
        raise httpx.ConnectError("no route")

    monkeypatch.setattr(tg_client.httpx, "post", boom)
    with pytest.raises(tg_client.TelegramTransientError):
        tg_client.send_message(1, "hi")


def test_reply_buttons_convert_to_aiogram_keyboard():
    from app.bot.handlers import _keyboard

    markup = _keyboard(
        [
            [{"text": "Details", "callback_data": "app:1:0"}],
            [{"text": "Site", "url": "https://hr.example.com/candidate/applications/1"}],
        ]
    )
    assert markup.inline_keyboard[0][0].callback_data == "app:1:0"
    assert markup.inline_keyboard[1][0].url.endswith("/applications/1")
    assert _keyboard([]) is None
