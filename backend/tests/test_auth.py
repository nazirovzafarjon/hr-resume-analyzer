"""Tests for authentication: register, login, logout, password reset.

Covers both the HTTP endpoints and the auth service functions
(``app.services.auth``).
"""

from datetime import timedelta

import pytest

from app.core.security import create_access_token, decode_access_token
from app.crud.user import count_users, get_user_by_email
from app.models.user import User
from app.schemas.auth import RegisterRequest
from app.services.auth import (
    authenticate_user,
    issue_token,
    register_user as service_register_user,
    reset_password,
    send_reset_email,
)

# Deterministic credentials used for the registered test user.
EMAIL = "hr@example.com"
PASSWORD = "StrongPassword123"


def login(client, email=EMAIL, password=PASSWORD):
    """POST /api/auth/login and return the response."""
    return client.post("/api/auth/login", json={"email": email, "password": password})


def _create_service_user(db_session, email="service@example.com", password="ServicePass123"):
    """Register a user through the service layer (for service-level tests)."""
    return service_register_user(
        db_session,
        RegisterRequest(email=email, full_name="Service User", password=password),
    )


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------


class TestRegister:
    def test_register_creates_account_and_returns_token(self, client, user_factory):
        response = user_factory()
        assert response.status_code == 201
        body = response.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        # The token must identify the newly created user.
        user_id = int(decode_access_token(body["access_token"])["sub"])
        assert user_id > 0

    def test_register_saves_user_in_database(self, client, user_factory, db_session):
        response = user_factory()
        assert response.status_code == 201
        user = get_user_by_email(db_session, EMAIL)
        assert user is not None
        assert user.full_name == "HR User"
        assert user.is_active is True
        assert user.is_superuser is False

    def test_register_never_stores_plaintext_password(self, client, user_factory, db_session):
        user_factory()
        user = get_user_by_email(db_session, EMAIL)
        assert user is not None
        assert user.hashed_password != PASSWORD
        assert user.hashed_password.startswith("$2b$")  # bcrypt digest

    def test_register_with_duplicate_email(self, client, user_factory, db_session):
        assert user_factory().status_code == 201
        duplicate = user_factory()
        assert duplicate.status_code == 400
        assert "already exists" in duplicate.json()["detail"]
        assert count_users(db_session) == 1

    def test_register_with_invalid_email(self, client, user_factory):
        assert user_factory(email="not-an-email").status_code == 422

    def test_register_with_empty_full_name(self, client, user_factory):
        assert user_factory(full_name="").status_code == 422

    def test_register_with_missing_fields(self, client):
        assert client.post("/api/auth/register", json={}).status_code == 422


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


class TestLogin:
    def test_login_with_correct_credentials(self, client, user_factory):
        user_factory()
        response = login(client)
        assert response.status_code == 200
        body = response.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        assert int(decode_access_token(body["access_token"])["sub"]) > 0

    def test_login_with_wrong_password(self, client, user_factory):
        user_factory()
        response = login(client, password="wrong-password")
        assert response.status_code == 401
        assert response.json()["detail"] == "Incorrect email or password"

    def test_login_with_unknown_email(self, client):
        response = login(client, email="nobody@example.com")
        assert response.status_code == 401

    def test_login_with_invalid_email_format(self, client):
        response = login(client, email="not-an-email")
        assert response.status_code == 422

    def test_login_rejects_deactivated_user(self, client, user_factory, db_session):
        """Deactivated accounts (is_active=False) must not be able to log in."""
        user_factory()
        user = get_user_by_email(db_session, EMAIL)
        assert user is not None
        user.is_active = False
        db_session.commit()

        assert login(client).status_code == 401

    def test_login_with_random_credentials_fails(self, client):
        """Arbitrary/random credentials must never authenticate."""
        response = login(client, email="random123@example.com", password="randomPassword123")
        assert response.status_code == 401
        assert response.json()["detail"] == "Incorrect email or password"

    def test_login_rejects_google_only_account_with_arbitrary_password(self, client, db_session):
        """Google-only accounts (hashed_password=None) cannot log in with arbitrary passwords."""
        from app.crud.user import get_or_create_google_user
        get_or_create_google_user(
            db_session,
            google_id="google-sub-789",
            email="google.only@example.com",
            full_name="Google User",
            picture=None,
        )
        response = login(client, email="google.only@example.com", password="anyPassword123")
        assert response.status_code == 401

    def test_register_and_login_case_insensitive_email(self, client, user_factory):
        """Registration and login must handle mixed-case emails consistently."""
        reg_res = user_factory(email="CaseMix@Example.COM", password="StrongPassword123")
        assert reg_res.status_code == 201
        login_res = login(client, email="casemix@example.com", password="StrongPassword123")
        assert login_res.status_code == 200
# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------


class TestLogout:
    def test_logout_with_token_returns_204(self, client, user):
        response = client.post("/api/auth/logout", headers=user["headers"])
        assert response.status_code == 204

    def test_logout_without_token_returns_401(self, client):
        assert client.post("/api/auth/logout").status_code == 401


# ---------------------------------------------------------------------------
# Protected endpoints (JWT guard)
# ---------------------------------------------------------------------------


class TestAuthenticationGuard:
    def test_protected_endpoint_without_token(self, client):
        assert client.get("/api/jobs").status_code == 401

    def test_protected_endpoint_with_garbage_token(self, client):
        headers = {"Authorization": "Bearer not-a-jwt"}
        assert client.get("/api/jobs", headers=headers).status_code == 401

    def test_protected_endpoint_with_expired_token(self, client):
        token = create_access_token(subject=1, expires_delta=timedelta(minutes=-1))
        headers = {"Authorization": f"Bearer {token}"}
        assert client.get("/api/jobs", headers=headers).status_code == 401

    def test_protected_endpoint_with_token_of_deleted_user(self, client, db_session):
        user = _create_service_user(db_session)
        token = issue_token(user)
        db_session.delete(user)
        db_session.commit()
        headers = {"Authorization": f"Bearer {token.access_token}"}
        assert client.get("/api/jobs", headers=headers).status_code == 401

    def test_protected_endpoint_with_valid_token(self, client, user):
        assert client.get("/api/jobs", headers=user["headers"]).status_code == 200


# ---------------------------------------------------------------------------
# Forgot / reset password
# ---------------------------------------------------------------------------


class TestPasswordReset:
    def test_forgot_password_returns_message_for_known_email(self, client, user_factory):
        user_factory()
        response = client.post("/api/auth/forgot-password", json={"email": EMAIL})
        assert response.status_code == 200
        assert "reset link" in response.json()["message"]

    def test_forgot_password_hides_whether_email_exists(self, client, user_factory):
        user_factory()
        known = client.post("/api/auth/forgot-password", json={"email": EMAIL})
        unknown = client.post("/api/auth/forgot-password", json={"email": "nobody@example.com"})
        assert known.status_code == 200
        assert known.json() == unknown.json()

    def test_reset_password_with_valid_token(self, client, user_factory):
        user_factory()
        # send_reset_email() issues short-lived tokens; reproduce it directly.
        token = create_access_token(subject=1, expires_delta=timedelta(minutes=30))
        response = client.post(
            "/api/auth/reset-password",
            json={"token": token, "new_password": "BrandNewPassword123"},
        )
        assert response.status_code == 200
        assert login(client, password=PASSWORD).status_code == 401
        assert login(client, password="BrandNewPassword123").status_code == 200

    def test_reset_password_with_invalid_token(self, client, user_factory):
        user_factory()
        response = client.post(
            "/api/auth/reset-password",
            json={"token": "invalid-token", "new_password": "BrandNewPassword123"},
        )
        assert response.status_code == 400

    def test_reset_password_with_expired_token(self, client, user_factory):
        user_factory()
        token = create_access_token(subject=1, expires_delta=timedelta(minutes=-5))
        response = client.post(
            "/api/auth/reset-password",
            json={"token": token, "new_password": "BrandNewPassword123"},
        )
        assert response.status_code == 400
# ---------------------------------------------------------------------------
# Auth service functions
# ---------------------------------------------------------------------------


class TestAuthService:
    def test_authenticate_user_returns_user(self, db_session):
        _create_service_user(db_session)
        user = authenticate_user(db_session, "service@example.com", "ServicePass123")
        assert isinstance(user, User)
        assert user.email == "service@example.com"

    def test_authenticate_user_with_wrong_password(self, db_session):
        _create_service_user(db_session)
        assert authenticate_user(db_session, "service@example.com", "wrong") is None

    def test_authenticate_user_with_unknown_email(self, db_session):
        assert authenticate_user(db_session, "nobody@example.com", "whatever") is None

    def test_authenticate_user_rejects_inactive_user(self, db_session):
        user = _create_service_user(db_session)
        user.is_active = False
        db_session.commit()
        assert authenticate_user(db_session, "service@example.com", "ServicePass123") is None

    def test_register_user_with_duplicate_email_raises(self, db_session):
        _create_service_user(db_session)
        with pytest.raises(ValueError):
            _create_service_user(db_session, email="service@example.com")

    def test_issue_token_returns_bearer_token(self, db_session):
        user = _create_service_user(db_session)
        token = issue_token(user)
        assert token.token_type == "bearer"
        assert decode_access_token(token.access_token)["sub"] == str(user.id)

    def test_send_reset_email_for_unknown_email_is_silent(self, db_session):
        # Must not raise and must not reveal whether the email is registered.
        assert send_reset_email(db_session, "nobody@example.com") is None

    def test_reset_password_updates_the_hash(self, db_session):
        user = _create_service_user(db_session)
        token = create_access_token(subject=user.id, expires_delta=timedelta(minutes=30))
        reset_password(db_session, token, "NewServicePass123")
        assert authenticate_user(db_session, "service@example.com", "NewServicePass123") is not None
        assert authenticate_user(db_session, "service@example.com", "ServicePass123") is None

    def test_reset_password_with_invalid_token_raises(self, db_session):
        with pytest.raises(ValueError):
            reset_password(db_session, "invalid-token", "NewServicePass123")