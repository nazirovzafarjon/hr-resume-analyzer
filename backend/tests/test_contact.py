"""Tests for the public Contact Us endpoint (POST /api/public/contact)."""

import pytest

from app.models.contact_message import ContactMessage
from app.services import contact_message as contact_message_service

CONTACT_URL = "/api/public/contact"
VALID_PAYLOAD = {
    "first_name": "Ada",
    "last_name": "Lovelace",
    "email": "ada@example.com",
    "message": "Hello! I'd like a demo of Resume Analyzer for our team.",
}


@pytest.fixture(autouse=True)
def _reset_contact_rate_limit():
    """Every test starts with a fresh per-client budget."""
    contact_message_service.reset_rate_limit()
    yield
    contact_message_service.reset_rate_limit()


def _stored(db_session) -> list[ContactMessage]:
    db_session.expire_all()
    return db_session.query(ContactMessage).all()


class TestSubmitContactMessage:
    def test_anonymous_visitor_can_send_a_message(self, client, db_session):
        response = client.post(CONTACT_URL, json=VALID_PAYLOAD)

        assert response.status_code == 201, response.text
        assert response.json() == {
            "message": "Thanks for reaching out! We'll get back to you soon."
        }
        [stored] = _stored(db_session)
        assert stored.first_name == "Ada"
        assert stored.last_name == "Lovelace"
        assert stored.email == "ada@example.com"
        assert stored.message == VALID_PAYLOAD["message"]
        assert stored.created_at is not None

    def test_signed_in_user_can_send_a_message(self, client, user, db_session):
        response = client.post(CONTACT_URL, json=VALID_PAYLOAD, headers=user["headers"])

        assert response.status_code == 201, response.text
        assert len(_stored(db_session)) == 1

    def test_invalid_bearer_token_is_ignored(self, client, db_session):
        response = client.post(
            CONTACT_URL, json=VALID_PAYLOAD, headers={"Authorization": "Bearer nope"}
        )

        assert response.status_code == 201, response.text

    def test_trims_surrounding_whitespace(self, client, db_session):
        payload = {
            **VALID_PAYLOAD,
            "first_name": "  Ada ",
            "email": "  Ada@Example.com ",
            "message": "\n Hi there \n",
        }

        response = client.post(CONTACT_URL, json=payload)

        assert response.status_code == 201, response.text
        [stored] = _stored(db_session)
        assert stored.first_name == "Ada"
        assert stored.message == "Hi there"
        assert stored.email.lower() == "ada@example.com"

    def test_response_does_not_echo_internal_data(self, client):
        body = client.post(CONTACT_URL, json=VALID_PAYLOAD).json()

        assert set(body) == {"message"}


class TestContactValidation:
    @pytest.mark.parametrize("field", ["first_name", "last_name", "email", "message"])
    def test_missing_field_is_rejected(self, client, db_session, field):
        payload = {key: value for key, value in VALID_PAYLOAD.items() if key != field}

        response = client.post(CONTACT_URL, json=payload)

        assert response.status_code == 422
        assert _stored(db_session) == []

    @pytest.mark.parametrize("field", ["first_name", "last_name", "message"])
    def test_blank_field_is_rejected(self, client, db_session, field):
        response = client.post(CONTACT_URL, json={**VALID_PAYLOAD, field: "   "})

        assert response.status_code == 422
        assert _stored(db_session) == []

    @pytest.mark.parametrize(
        "email", ["", "abc", "test", "hello@", "@example.com", "a b@example.com"]
    )
    def test_invalid_email_is_rejected(self, client, db_session, email):
        response = client.post(CONTACT_URL, json={**VALID_PAYLOAD, "email": email})

        assert response.status_code == 422
        assert _stored(db_session) == []

    def test_all_invalid_fields_are_reported_together(self, client, db_session):
        response = client.post(
            CONTACT_URL,
            json={"first_name": "", "last_name": "", "email": "abc", "message": ""},
        )

        assert response.status_code == 422
        fields = {error["loc"][-1] for error in response.json()["detail"]}
        assert fields == {"first_name", "last_name", "email", "message"}
        assert _stored(db_session) == []

    def test_overlong_values_are_rejected(self, client, db_session):
        too_long_name = client.post(
            CONTACT_URL, json={**VALID_PAYLOAD, "first_name": "a" * 101}
        )
        too_long_message = client.post(
            CONTACT_URL, json={**VALID_PAYLOAD, "message": "a" * 5001}
        )

        assert too_long_name.status_code == 422
        assert too_long_message.status_code == 422
        assert _stored(db_session) == []

    def test_long_but_reasonable_message_is_accepted(self, client):
        response = client.post(CONTACT_URL, json={**VALID_PAYLOAD, "message": "a" * 5000})

        assert response.status_code == 201, response.text


class TestContactRateLimit:
    def test_rejects_bursts_from_one_client(self, client, db_session):
        limit = contact_message_service.RATE_LIMIT_MAX_MESSAGES
        for _ in range(limit):
            assert client.post(CONTACT_URL, json=VALID_PAYLOAD).status_code == 201

        response = client.post(CONTACT_URL, json=VALID_PAYLOAD)

        assert response.status_code == 429
        assert response.json() == {"detail": "Too many messages. Please try again later."}
        assert len(_stored(db_session)) == limit

    def test_invalid_submissions_do_not_use_the_budget(self, client):
        for _ in range(contact_message_service.RATE_LIMIT_MAX_MESSAGES + 2):
            assert client.post(CONTACT_URL, json={}).status_code == 422

        assert client.post(CONTACT_URL, json=VALID_PAYLOAD).status_code == 201
