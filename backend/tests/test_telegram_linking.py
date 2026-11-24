"""Telegram account linking: API endpoints, token rules and bot commands."""

from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest

from app.bot import actions
from app.core.config import settings
from app.core.security import create_candidate_email_verification_token
from app.models.audit_log import AuditLog
from app.models.telegram_link import TelegramAccountKind, TelegramLink, TelegramLinkToken
from app.models.user import User
from app.services.telegram import linking
from app.services.telegram.linking import TelegramProfile, hash_token

TG_USER = 555_000_111


@pytest.fixture
def telegram_on(monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_ENABLED", True)
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "123:test-token")
    monkeypatch.setattr(settings, "TELEGRAM_BOT_USERNAME", "ra_test_bot")


def _profile(telegram_user_id=TG_USER, language_code="uz"):
    return TelegramProfile(
        telegram_user_id=telegram_user_id,
        chat_id=telegram_user_id,
        username="jane_tg",
        first_name="Jane",
        language_code=language_code,
    )


def _token_from(deep_link: str) -> str:
    parsed = urlparse(deep_link)
    assert parsed.netloc == "t.me" and parsed.path == "/ra_test_bot"
    return parse_qs(parsed.query)["start"][0]


def _issue(client, headers, kind="hr") -> str:
    response = client.post(f"/api/telegram/{kind}/link-token", headers=headers)
    assert response.status_code == 200, response.text
    return _token_from(response.json()["deep_link"])


@pytest.fixture
def candidate(client):
    response = client.post(
        "/api/candidate/auth/register",
        json={"email": "jane@example.com", "full_name": "Jane", "password": "CandidatePass1"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    client.post(
        "/api/candidate/auth/verify-email",
        json={"token": create_candidate_email_verification_token(body["candidate"]["id"])},
    )
    return {
        "id": body["candidate"]["id"],
        "headers": {"Authorization": f"Bearer {body['access_token']}"},
    }


# --- API ---------------------------------------------------------------------


def test_status_reports_disabled_bot(client, user):
    response = client.get("/api/telegram/hr/link", headers=user["headers"])
    assert response.status_code == 200
    assert response.json()["enabled"] is False
    assert response.json()["linked"] is False


def test_link_token_requires_configured_bot(client, user):
    response = client.post("/api/telegram/hr/link-token", headers=user["headers"])
    assert response.status_code == 503


def test_endpoints_require_authentication(client, telegram_on):
    assert client.get("/api/telegram/hr/link").status_code == 401
    assert client.post("/api/telegram/candidate/link-token").status_code == 401


def test_tokens_cannot_cross_identities(client, user, candidate, telegram_on):
    assert client.get("/api/telegram/candidate/link", headers=user["headers"]).status_code == 401
    assert client.get("/api/telegram/hr/link", headers=candidate["headers"]).status_code == 401


def test_only_digest_of_token_is_stored(client, user, telegram_on, db_session):
    raw = _issue(client, user["headers"])
    stored = db_session.query(TelegramLinkToken).one()
    assert stored.token_hash == hash_token(raw)
    assert raw not in stored.token_hash


def test_hr_full_link_and_unlink_flow(client, user, telegram_on, db_session):
    raw = _issue(client, user["headers"])

    reply = actions.start(_profile(), raw)
    assert "HR" in reply and user["email"] in reply

    status = client.get("/api/telegram/hr/link", headers=user["headers"]).json()
    assert status["enabled"] is True and status["linked"] is True
    assert status["username"] == "jane_tg" and status["bot_username"] == "ra_test_bot"

    actions_in_log = {row.action for row in db_session.query(AuditLog).all()}
    assert "TELEGRAM_LINKED" in actions_in_log

    assert client.delete("/api/telegram/hr/link", headers=user["headers"]).status_code == 204
    assert client.get("/api/telegram/hr/link", headers=user["headers"]).json()["linked"] is False
    assert client.delete("/api/telegram/hr/link", headers=user["headers"]).status_code == 404


def test_candidate_link_flow(client, candidate, telegram_on, db_session):
    raw = _issue(client, candidate["headers"], kind="candidate")
    reply = actions.start(_profile(language_code="en"), raw)
    assert "candidate account" in reply

    link = db_session.query(TelegramLink).one()
    assert link.kind == TelegramAccountKind.CANDIDATE
    assert link.candidate_account_id == candidate["id"] and link.user_id is None
    assert link.language == "en"


def test_one_telegram_account_can_hold_hr_and_candidate_links(
    client, user, candidate, telegram_on, db_session
):
    actions.start(_profile(), _issue(client, user["headers"]))
    actions.start(_profile(), _issue(client, candidate["headers"], kind="candidate"))
    assert db_session.query(TelegramLink).count() == 2
    reply = actions.status(_profile())
    assert "HR" in reply and "Nomzod" in reply


# --- token rules -------------------------------------------------------------


def test_token_is_single_use(client, user, telegram_on):
    raw = _issue(client, user["headers"])
    actions.start(_profile(), raw)
    assert "ishlatilgan" in actions.start(_profile(telegram_user_id=999), raw)


def test_new_token_supersedes_older_one(client, user, telegram_on):
    first = _issue(client, user["headers"])
    second = _issue(client, user["headers"])
    assert "ishlatilgan" in actions.start(_profile(), first)
    assert "✅" in actions.start(_profile(), second)


def test_expired_token_is_rejected(client, user, telegram_on, db_session):
    raw = _issue(client, user["headers"])
    token = db_session.query(TelegramLinkToken).one()
    token.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()
    assert "muddati" in actions.start(_profile(), raw)
    assert db_session.query(TelegramLink).count() == 0


def test_unknown_token_is_rejected(telegram_on):
    with pytest.raises(linking.LinkTokenError) as exc:
        from app.core.database import SessionLocal

        with SessionLocal() as db:
            linking.consume_link_token(db, "not-a-real-token", _profile())
    assert exc.value.code == "invalid"


def test_deactivated_account_cannot_link(client, user, telegram_on, db_session):
    raw = _issue(client, user["headers"])
    db_session.get(User, user["id"]).is_active = False
    db_session.commit()
    assert "⛔" in actions.start(_profile(), raw)


def test_relinking_moves_the_chat(client, user, telegram_on, db_session):
    actions.start(_profile(telegram_user_id=1), _issue(client, user["headers"]))
    actions.start(_profile(telegram_user_id=2), _issue(client, user["headers"]))
    links = db_session.query(TelegramLink).all()
    assert [link.telegram_user_id for link in links] == [2]


def test_same_telegram_user_moves_between_hr_accounts(
    client, user, other_user, telegram_on, db_session
):
    actions.start(_profile(), _issue(client, user["headers"]))
    actions.start(_profile(), _issue(client, other_user["headers"]))
    links = db_session.query(TelegramLink).all()
    assert [link.user_id for link in links] == [other_user["id"]]


# --- bot commands ------------------------------------------------------------


def test_start_without_token_greets_unlinked_user(telegram_on):
    assert "Sozlamalar" in actions.start(_profile(), None)
    assert "Настройки" in actions.start(_profile(language_code="ru"), None)


def test_start_without_token_shows_status_when_linked(client, user, telegram_on):
    actions.start(_profile(), _issue(client, user["headers"]))
    assert user["email"] in actions.start(_profile(), None)


def test_bot_unlink_removes_all_links(client, user, candidate, telegram_on, db_session):
    actions.start(_profile(), _issue(client, user["headers"]))
    actions.start(_profile(), _issue(client, candidate["headers"], kind="candidate"))
    assert "uzildi" in actions.unlink(_profile())
    assert db_session.query(TelegramLink).count() == 0
    assert "yo'q" in actions.unlink(_profile())


def test_status_hides_deactivated_accounts(client, user, telegram_on, db_session):
    actions.start(_profile(), _issue(client, user["headers"]))
    db_session.get(User, user["id"]).is_active = False
    db_session.commit()
    assert "ulanmagan" in actions.status(_profile())


def test_language_normalisation():
    assert linking.normalize_language("ru-RU") == "ru"
    assert linking.normalize_language("de") == "uz"
    assert linking.normalize_language(None) == "uz"
