"""Tests for the forgot / reset / skip password workflow.

Covers the three endpoints that a reset link drives
(``POST /api/auth/forgot-password``, ``/reset-password``, ``/skip-reset`` and
``/verify-reset-token``), the access/refresh pair they issue, and the rules that
keep the three token purposes apart:

* a reset token only works on the reset endpoints — never as a bearer token;
* a refresh token only works on ``POST /api/auth/refresh`` — never as a bearer
  token and never as reset credentials;
* changing the password revokes sessions issued before the change, while
  skipping the reset leaves every existing session alone.
"""

from datetime import timedelta

import pytest

from app.core.security import (
    create_password_reset_token,
    create_refresh_token,
    decode_access_token,
)
from app.crud.user import get_or_create_google_user, get_user_by_email
from app.services.auth import (
    authenticate_user,
    issue_token,
    refresh_access_token,
    register_user as service_register_user,
    resolve_reset_token,
    send_reset_email,
    skip_reset,
)
from app.schemas.auth import RegisterRequest

EMAIL = "hr@example.com"
PASSWORD = "StrongPassword123"
GOOGLE_EMAIL = "google@example.com"
GOOGLE_ID = "google-only-123"
NEW_PASSWORD = "BrandNewPassword123"


def _login(client, email=EMAIL, password=PASSWORD):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def _register(client, email=EMAIL, password=PASSWORD):
    """Register and confirm the email so the panel is reachable.

    Registration alone leaves the account unverified; these tests exercise the
    reset/refresh flows and their resulting sessions, so they confirm the email
    first (the verification flow itself is covered in test_email_verification).
    """
    from tests.conftest import verify_registered_user

    response = client.post(
        "/api/auth/register",
        json={"email": email, "full_name": "HR User", "password": password},
    )
    return verify_registered_user(client, response, email)


def _create_service_user(db_session, email="service@example.com", password="ServicePass123"):
    return service_register_user(
        db_session,
        RegisterRequest(email=email, full_name="Service User", password=password),
    )


def _create_google_only_user(db_session, email=GOOGLE_EMAIL):
    """Create an account with a Google identity and no local password."""
    return get_or_create_google_user(
        db_session,
        google_id=GOOGLE_ID,
        email=email,
        full_name="Google Only User",
        picture=None,
    )


def _reset_token(db_session, email=EMAIL) -> str:
    """Mint the short-lived token an emailed reset link would carry."""
    user = get_user_by_email(db_session, email)
    assert user is not None, "test setup: the account must exist first"
    return create_password_reset_token(subject=user.id)


class TestResetIssuesASession:
    """Changing the password must leave the caller signed in."""

    def test_reset_returns_access_and_refresh_tokens(self, client, db_session):
        _register(client)
        response = client.post(
            "/api/auth/reset-password",
            json={"token": _reset_token(db_session), "new_password": NEW_PASSWORD},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["token_type"] == "bearer"
        assert decode_access_token(body["access_token"])["sub"] == "1"
        refresh_claims = decode_access_token(body["refresh_token"])
        assert refresh_claims["sub"] == "1"
        assert refresh_claims["typ"] == "refresh"

    def test_reset_issued_token_authorizes_api_requests(self, client, db_session):
        _register(client)
        body = client.post(
            "/api/auth/reset-password",
            json={"token": _reset_token(db_session), "new_password": NEW_PASSWORD},
        ).json()
        headers = {"Authorization": f"Bearer {body['access_token']}"}
        assert client.get("/api/jobs", headers=headers).status_code == 200

    def test_reset_invalidates_sessions_issued_before_the_change(self, client, user, db_session):
        """A password change logs every other device out (old bearer -> 401)."""
        client.post(
            "/api/auth/reset-password",
            json={"token": _reset_token(db_session), "new_password": NEW_PASSWORD},
        )
        assert client.get("/api/jobs", headers=user["headers"]).status_code == 401

    def test_reset_rejects_deactivated_account(self, client, db_session):
        _register(client)
        account = get_user_by_email(db_session, EMAIL)
        account.is_active = False
        db_session.commit()
        response = client.post(
            "/api/auth/reset-password",
            json={"token": _reset_token(db_session), "new_password": NEW_PASSWORD},
        )
        assert response.status_code == 400



class TestTokenPurposeIsolation:
    """Each token may only be used for the purpose it was minted for."""

    def test_reset_token_cannot_be_used_as_a_session(self, client, db_session):
        # A reset token travels inside an emailed URL, so it must not authenticate
        # the API even though it is a correctly signed, unexpired JWT.
        _register(client)
        headers = {"Authorization": f"Bearer {_reset_token(db_session)}"}
        assert client.get("/api/jobs", headers=headers).status_code == 401

    def test_refresh_token_cannot_be_used_as_a_session(self, client, db_session):
        _register(client)
        headers = {"Authorization": f"Bearer {create_refresh_token(subject=1)}"}
        assert client.get("/api/jobs", headers=headers).status_code == 401

    def test_refresh_token_cannot_reset_a_password(self, client, db_session):
        _register(client)
        response = client.post(
            "/api/auth/reset-password",
            json={"token": create_refresh_token(subject=1), "new_password": NEW_PASSWORD},
        )
        assert response.status_code == 400

    def test_refresh_token_cannot_be_skipped_with(self, client, db_session):
        _register(client)
        response = client.post(
            "/api/auth/skip-reset", json={"token": create_refresh_token(subject=1)}
        )
        assert response.status_code == 400


class TestGoogleOAuthAccounts:
    """Google-only accounts have no password; the flow must cope either way."""

    def test_forgot_password_reply_is_identical_for_every_account(self, client, db_session):
        """Never reveal the account type — or whether the email exists at all."""
        _register(client)
        _create_google_only_user(db_session)
        password_account = client.post(
            "/api/auth/forgot-password", json={"email": EMAIL}
        )
        google_account = client.post(
            "/api/auth/forgot-password", json={"email": GOOGLE_EMAIL}
        )
        unknown = client.post("/api/auth/forgot-password", json={"email": "nobody@example.com"})
        assert password_account.status_code == 200
        assert password_account.json() == google_account.json() == unknown.json()

    def test_skip_signs_in_an_account_without_a_password(self, client, db_session):
        google_user = _create_google_only_user(db_session)
        response = client.post(
            "/api/auth/skip-reset",
            json={"token": create_password_reset_token(subject=google_user.id)},
        )
        assert response.status_code == 200
        body = response.json()
        assert decode_access_token(body["access_token"])["sub"] == str(google_user.id)
        db_session.expire_all()
        assert get_user_by_email(db_session, GOOGLE_EMAIL).hashed_password is None

    def test_reset_adds_a_local_password_without_unlinking_google(self, client, db_session):
        google_user = _create_google_only_user(db_session)
        response = client.post(
            "/api/auth/reset-password",
            json={
                "token": create_password_reset_token(subject=google_user.id),
                "new_password": "LocalPassword123",
            },
        )
        assert response.status_code == 200
        db_session.expire_all()
        account = get_user_by_email(db_session, GOOGLE_EMAIL)
        assert account.google_id == GOOGLE_ID  # Google sign-in still works
        assert authenticate_user(db_session, GOOGLE_EMAIL, "LocalPassword123") is not None

    def test_verify_endpoint_reports_the_missing_local_password(self, client, db_session):
        google_user = _create_google_only_user(db_session)
        response = client.post(
            "/api/auth/verify-reset-token",
            json={"token": create_password_reset_token(subject=google_user.id)},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["email"] == GOOGLE_EMAIL
        assert body["has_password"] is False
        assert body["is_google_account"] is True


class TestVerifyResetToken:
    def test_describes_a_password_account(self, client, db_session):
        _register(client)
        response = client.post(
            "/api/auth/verify-reset-token", json={"token": _reset_token(db_session)}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["email"] == EMAIL
        assert body["full_name"] == "HR User"
        assert body["has_password"] is True
        assert body["is_google_account"] is False

    def test_rejects_garbage(self, client):
        assert client.post(
            "/api/auth/verify-reset-token", json={"token": "not-a-jwt"}
        ).status_code == 400

    def test_rejects_expired_token(self, client, db_session):
        _register(client)
        expired = create_password_reset_token(
            subject=1, expires_delta=timedelta(minutes=-1)
        )
        assert client.post(
            "/api/auth/verify-reset-token", json={"token": expired}
        ).status_code == 400

    def test_requires_a_token(self, client):
        assert client.post(
            "/api/auth/verify-reset-token", json={}
        ).status_code == 422


class TestSkipReset:
    """The "Skip" button: keep the password, mint a session from the link."""

    def test_skip_returns_a_working_session(self, client, db_session):
        _register(client)
        response = client.post(
            "/api/auth/skip-reset", json={"token": _reset_token(db_session)}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["token_type"] == "bearer"
        headers = {"Authorization": f"Bearer {body['access_token']}"}
        assert client.get("/api/jobs", headers=headers).status_code == 200

    def test_skip_leaves_the_password_unchanged(self, client, db_session):
        _register(client)
        client.post("/api/auth/skip-reset", json={"token": _reset_token(db_session)})
        assert _login(client).status_code == 200

    def test_skip_keeps_other_sessions_alive(self, client, user, db_session):
        """Unlike a password change, skipping must not log anyone else out."""
        client.post("/api/auth/skip-reset", json={"token": _reset_token(db_session)})
        assert client.get("/api/jobs", headers=user["headers"]).status_code == 200

    def test_skip_rejects_garbage(self, client):
        assert client.post(
            "/api/auth/skip-reset", json={"token": "invalid-token"}
        ).status_code == 400

    def test_skip_rejects_expired_token(self, client, db_session):
        _register(client)
        expired = create_password_reset_token(
            subject=1, expires_delta=timedelta(minutes=-1)
        )
        assert client.post(
            "/api/auth/skip-reset", json={"token": expired}
        ).status_code == 400

    def test_skip_rejects_token_of_a_deleted_account(self, client, db_session):
        account = _create_service_user(db_session)
        token = create_password_reset_token(subject=account.id)
        db_session.delete(account)
        db_session.commit()
        assert client.post(
            "/api/auth/skip-reset", json={"token": token}
        ).status_code == 400

    def test_skip_requires_a_token(self, client):
        assert client.post("/api/auth/skip-reset", json={}).status_code == 422


class TestTokenRefresh:
    """POST /api/auth/refresh — exchange the refresh token for a new pair."""

    def _fresh_pair(self, client, db_session):
        _register(client)
        return _login(client).json()

    def test_refresh_returns_a_new_pair(self, client, db_session):
        pair = self._fresh_pair(client, db_session)
        response = client.post(
            "/api/auth/refresh", json={"refresh_token": pair["refresh_token"]}
        )
        assert response.status_code == 200
        rotated = response.json()
        assert rotated["access_token"] != pair["access_token"]
        assert decode_access_token(rotated["access_token"])["sub"] == "1"

    def test_refreshed_token_authorizes_api_requests(self, client, db_session):
        pair = self._fresh_pair(client, db_session)
        rotated = client.post(
            "/api/auth/refresh", json={"refresh_token": pair["refresh_token"]}
        ).json()
        headers = {"Authorization": f"Bearer {rotated['access_token']}"}
        assert client.get("/api/jobs", headers=headers).status_code == 200

    def test_refresh_token_is_single_use(self, client, db_session):
        """Replaying a consumed refresh token must fail (rotation)."""
        pair = self._fresh_pair(client, db_session)
        payload = {"refresh_token": pair["refresh_token"]}
        assert client.post("/api/auth/refresh", json=payload).status_code == 200
        assert client.post("/api/auth/refresh", json=payload).status_code == 401

    def test_refresh_rejects_an_access_token(self, client, db_session):
        pair = self._fresh_pair(client, db_session)
        response = client.post(
            "/api/auth/refresh", json={"refresh_token": pair["access_token"]}
        )
        assert response.status_code == 401

    def test_refresh_rejects_garbage(self, client):
        response = client.post("/api/auth/refresh", json={"refresh_token": "nonsense"})
        assert response.status_code == 401

    def test_refresh_rejects_deactivated_account(self, client, db_session):
        pair = self._fresh_pair(client, db_session)
        account = get_user_by_email(db_session, EMAIL)
        account.is_active = False
        db_session.commit()
        response = client.post(
            "/api/auth/refresh", json={"refresh_token": pair["refresh_token"]}
        )
        assert response.status_code == 401

    def test_refresh_requires_a_token(self, client):
        assert client.post("/api/auth/refresh", json={}).status_code == 422


class TestResetServiceLayer:
    """The same guarantees one level down, without the HTTP wrapper."""

    def test_send_reset_email_returns_nothing_for_known_and_unknown_emails(self, db_session):
        # The void return is what keeps the endpoint free of account details.
        _create_service_user(db_session)
        assert send_reset_email(db_session, "service@example.com") is None
        assert send_reset_email(db_session, "nobody@example.com") is None

    def test_send_reset_email_forwards_the_token_to_the_mailer(self, db_session, monkeypatch):
        """The auth service must hand the freshly minted token to Resend."""
        account = _create_service_user(db_session)
        calls: list[tuple[str, str]] = []

        def fake_mailer(email: str, token: str) -> bool:
            calls.append((email, token))
            return True

        monkeypatch.setattr("app.services.auth.send_reset_password_email", fake_mailer)

        assert send_reset_email(db_session, "service@example.com") is None
        assert len(calls) == 1
        recipient, token = calls[0]
        assert recipient == "service@example.com"
        # The delivered token must be a signed, short-lived password_reset JWT
        # for the same account — never a session credential.
        claims = decode_access_token(token)
        assert claims["sub"] == str(account.id)
        assert claims["typ"] == "password_reset"

    def test_send_reset_email_falls_back_to_logging_when_delivery_fails(
        self, db_session, monkeypatch
    ):
        """A mailer failure must not surface to the caller (no enumeration)."""
        _create_service_user(db_session)
        monkeypatch.setattr(
            "app.services.auth.send_reset_password_email", lambda email, token: False
        )
        assert send_reset_email(db_session, "service@example.com") is None
        assert send_reset_email(db_session, "nobody@example.com") is None

    def test_skip_returns_a_pair_and_keeps_the_password(self, db_session):
        account = _create_service_user(db_session)
        tokens = skip_reset(db_session, create_password_reset_token(subject=account.id))
        assert decode_access_token(tokens.access_token)["sub"] == str(account.id)
        assert decode_access_token(tokens.refresh_token)["typ"] == "refresh"
        assert authenticate_user(db_session, "service@example.com", "ServicePass123") is not None

    def test_skip_rejects_expired_token(self, db_session):
        account = _create_service_user(db_session)
        expired = create_password_reset_token(
            subject=account.id, expires_delta=timedelta(minutes=-1)
        )
        with pytest.raises(ValueError):
            skip_reset(db_session, expired)

    def test_refresh_rotates_both_tokens(self, db_session):
        account = _create_service_user(db_session)
        first = issue_token(account)
        second = refresh_access_token(db_session, first.refresh_token)
        assert second.access_token != first.access_token
        assert second.refresh_token != first.refresh_token

    def test_refresh_rejects_replay(self, db_session):
        account = _create_service_user(db_session)
        first = issue_token(account)
        refresh_access_token(db_session, first.refresh_token)
        with pytest.raises(ValueError):
            refresh_access_token(db_session, first.refresh_token)

    def test_refresh_rejects_access_purpose_token(self, db_session):
        account = _create_service_user(db_session)
        with pytest.raises(ValueError):
            refresh_access_token(db_session, issue_token(account).access_token)

    def test_resolve_rejects_deactivated_account(self, db_session):
        account = _create_service_user(db_session)
        account.is_active = False
        db_session.commit()
        with pytest.raises(ValueError):
            resolve_reset_token(db_session, create_password_reset_token(subject=account.id))

    def test_issue_token_keeps_the_bearer_contract(self, db_session):
        """Login/register responses are unchanged apart from the added field."""
        account = _create_service_user(db_session)
        tokens = issue_token(account)
        assert tokens.token_type == "bearer"
        assert decode_access_token(tokens.access_token)["sub"] == str(account.id)
