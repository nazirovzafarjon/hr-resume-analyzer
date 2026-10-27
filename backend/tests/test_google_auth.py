"""Tests for the Google OAuth (Sign in with Google) integration.

Covers:
* ``app.services.google_auth`` - code exchange + userinfo fetch (with httpx
  MockTransport, so no real network calls are made).
* ``app.crud.user.get_or_create_google_user`` - account creation/linking.
* ``app.services.auth.login_with_google`` - end-to-end service flow.
* ``POST /api/auth/google`` - the HTTP endpoint.
"""

import httpx
import pytest
from urllib.parse import parse_qs

from app.core.config import settings
from app.core.security import decode_access_token
from app.crud.user import get_or_create_google_user, get_user_by_email
from app.models.user import User
from app.schemas.auth import Token
from app.services import auth as auth_service
from app.services.google_auth import (
    GOOGLE_TOKEN_URL,
    GOOGLE_USERINFO_URL,
    POSTMESSAGE_REDIRECT_URI,
    GoogleAuthError,
    GoogleAuthService,
    GoogleUserProfile,
)

GOOGLE_ID = "113987654321098765432"
GOOGLE_EMAIL = "hr.google@example.com"
GOOGLE_NAME = "HR Google User"
GOOGLE_PICTURE = "https://lh3.googleusercontent.com/example/photo.jpg"

_FAKE_TOKENS = {
    "access_token": "ya29.fake-access-token",
    "token_type": "Bearer",
    "expires_in": 3599,
    "id_token": "header.payload.signature",
}

_FAKE_USERINFO = {
    "sub": GOOGLE_ID,
    "email": GOOGLE_EMAIL,
    "name": GOOGLE_NAME,
    "picture": GOOGLE_PICTURE,
    "email_verified": True,
}


def _configure_google(monkeypatch):
    """Point settings at fake Google credentials so the service passes its guard."""
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "fake-client-id.apps.googleusercontent.com")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "fake-client-secret")


def _mock_service(handler) -> GoogleAuthService:
    """Build a GoogleAuthService whose HTTP calls are served by ``handler``."""
    transport = httpx.MockTransport(handler)
    return GoogleAuthService(http_client=httpx.AsyncClient(transport=transport))


# ---------------------------------------------------------------------------
# Google service: code exchange
# ---------------------------------------------------------------------------


class TestExchangeCodeForTokens:
    @pytest.mark.anyio
    async def test_exchanges_code_for_tokens(self, monkeypatch):
        _configure_google(monkeypatch)

        async def handler(request: httpx.Request) -> httpx.Response:
            assert request.url == GOOGLE_TOKEN_URL
            assert request.headers["content-type"].startswith(
                "application/x-www-form-urlencoded"
            )
            return httpx.Response(200, json=_FAKE_TOKENS)

        service = _mock_service(handler)
        body = await service.exchange_code_for_tokens("auth-code-123")
        assert body["access_token"] == "ya29.fake-access-token"

    @pytest.mark.anyio
    async def test_rejected_code_raises_google_auth_error(self, monkeypatch):
        _configure_google(monkeypatch)

        async def handler(request):  # noqa: ARG001
            return httpx.Response(400, json={"error": "invalid_grant"})

        service = _mock_service(handler)
        with pytest.raises(GoogleAuthError):
            await service.exchange_code_for_tokens("bad-code")

    @pytest.mark.anyio
    async def test_unconfigured_settings_raise_before_network(self, monkeypatch):
        monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "")

        async def handler(request):  # noqa: ARG001
            return httpx.Response(200, json=_FAKE_TOKENS)

        service = _mock_service(handler)
        with pytest.raises(GoogleAuthError, match="not configured"):
            await service.exchange_code_for_tokens("code")

    @pytest.mark.anyio
    async def test_network_timeout_raises_google_auth_error(self, monkeypatch):
        _configure_google(monkeypatch)

        async def handler(request):  # noqa: ARG001
            raise httpx.ConnectTimeout("timed out", request=request)

        service = _mock_service(handler)
        with pytest.raises(GoogleAuthError, match="timed out"):
            await service.exchange_code_for_tokens("code")

    @pytest.mark.anyio
    async def test_missing_access_token_raises(self, monkeypatch):
        _configure_google(monkeypatch)

        async def handler(request):  # noqa: ARG001
            return httpx.Response(200, json={"error": "weird"})

        service = _mock_service(handler)
        with pytest.raises(GoogleAuthError):
            await service.exchange_code_for_tokens("code")

    @pytest.mark.anyio
    async def test_sends_client_redirect_uri_in_exchange(self, monkeypatch):
        """Popup-issued codes are bound to ``postmessage`` — exchange must match."""
        _configure_google(monkeypatch)
        seen: dict = {}

        async def handler(request: httpx.Request) -> httpx.Response:
            seen.update(parse_qs(request.content.decode()))
            return httpx.Response(200, json=_FAKE_TOKENS)

        service = _mock_service(handler)
        await service.exchange_code_for_tokens("code", POSTMESSAGE_REDIRECT_URI)
        assert seen["redirect_uri"] == ["postmessage"]

    @pytest.mark.anyio
    async def test_defaults_to_configured_redirect_uri(self, monkeypatch):
        _configure_google(monkeypatch)
        seen: dict = {}

        async def handler(request: httpx.Request) -> httpx.Response:
            seen.update(parse_qs(request.content.decode()))
            return httpx.Response(200, json=_FAKE_TOKENS)

        service = _mock_service(handler)
        await service.exchange_code_for_tokens("code")
        assert seen["redirect_uri"] == [settings.GOOGLE_REDIRECT_URI]

    @pytest.mark.anyio
    async def test_unrecognized_redirect_uri_is_rejected_before_network(self, monkeypatch):
        _configure_google(monkeypatch)

        async def handler(request):  # noqa: ARG001
            raise AssertionError("no network call expected")

        service = _mock_service(handler)
        with pytest.raises(GoogleAuthError, match="redirect URI"):
            await service.exchange_code_for_tokens(
                "code", "https://evil.example/callback"
            )


# ---------------------------------------------------------------------------
# Google service: userinfo + full authenticate flow
# ---------------------------------------------------------------------------


class TestFetchUserInfo:
    @pytest.mark.anyio
    async def test_fetches_profile(self):
        async def handler(request: httpx.Request) -> httpx.Response:
            assert request.url == GOOGLE_USERINFO_URL
            assert request.headers["authorization"] == "Bearer ya29.fake-access-token"
            return httpx.Response(200, json=_FAKE_USERINFO)

        service = _mock_service(handler)
        info = await service.fetch_user_info("ya29.fake-access-token")
        assert info["sub"] == GOOGLE_ID
        assert info["email"] == GOOGLE_EMAIL

    @pytest.mark.anyio
    async def test_rejected_token_raises(self):
        async def handler(request):  # noqa: ARG001
            return httpx.Response(401, json={"error": "invalid_token"})

        service = _mock_service(handler)
        with pytest.raises(GoogleAuthError):
            await service.fetch_user_info("bad-token")


class TestAuthenticate:
    @pytest.mark.anyio
    async def test_returns_normalized_profile(self, monkeypatch):
        _configure_google(monkeypatch)

        async def handler(request: httpx.Request) -> httpx.Response:
            if request.url == GOOGLE_TOKEN_URL:
                return httpx.Response(200, json=_FAKE_TOKENS)
            return httpx.Response(200, json=_FAKE_USERINFO)

        service = _mock_service(handler)
        profile = await service.authenticate("auth-code-123")
        assert profile == GoogleUserProfile(
            google_id=GOOGLE_ID,
            email=GOOGLE_EMAIL,
            full_name=GOOGLE_NAME,
            picture=GOOGLE_PICTURE,
        )

    @pytest.mark.anyio
    async def test_missing_email_logs_exact_userinfo_and_raises(self, monkeypatch, caplog):
        _configure_google(monkeypatch)
        userinfo = dict(_FAKE_USERINFO)
        userinfo.pop("email")

        async def handler(request: httpx.Request) -> httpx.Response:
            if request.url == GOOGLE_TOKEN_URL:
                return httpx.Response(200, json=_FAKE_TOKENS)
            return httpx.Response(200, json=userinfo)

        service = _mock_service(handler)
        with pytest.raises(GoogleAuthError, match="enough profile data"):
            await service.authenticate("auth-code-123")
        assert "Google userinfo missing required email or sub" in caplog.text
        assert str(userinfo) in caplog.text

    @pytest.mark.anyio
    async def test_derives_name_from_email_when_missing(self, monkeypatch):
        _configure_google(monkeypatch)
        userinfo = dict(_FAKE_USERINFO)
        userinfo.pop("name")

        async def handler(request: httpx.Request) -> httpx.Response:
            if request.url == GOOGLE_TOKEN_URL:
                return httpx.Response(200, json=_FAKE_TOKENS)
            return httpx.Response(200, json=userinfo)

        service = _mock_service(handler)
        profile = await service.authenticate("auth-code-123")
        assert profile.full_name == "Hr google"  # str.capitalize() behaviour


# ---------------------------------------------------------------------------
# CRUD: get_or_create_google_user
# ---------------------------------------------------------------------------


class TestGetOrCreateGoogleUser:
    def test_creates_new_google_account(self, db_session):
        user = get_or_create_google_user(
            db_session,
            google_id=GOOGLE_ID,
            email=GOOGLE_EMAIL,
            full_name=GOOGLE_NAME,
            picture=GOOGLE_PICTURE,
        )
        assert isinstance(user, User)
        assert user.id is not None
        assert user.google_id == GOOGLE_ID
        assert user.email == GOOGLE_EMAIL
        assert user.hashed_password is None  # Google users have no password
        assert user.is_active is True
        assert user.is_superuser is False

    def test_returns_same_row_on_second_call(self, db_session):
        first = get_or_create_google_user(
            db_session, google_id=GOOGLE_ID, email=GOOGLE_EMAIL,
            full_name=GOOGLE_NAME, picture=GOOGLE_PICTURE,
        )
        second = get_or_create_google_user(
            db_session, google_id=GOOGLE_ID, email=GOOGLE_EMAIL,
            full_name=GOOGLE_NAME, picture=GOOGLE_PICTURE,
        )
        assert first.id == second.id
        assert db_session.query(User).count() == 1

    def test_links_existing_password_account_by_email(self, db_session):
        existing = get_or_create_google_user(
            db_session, google_id=None, email=GOOGLE_EMAIL,
            full_name="Old Name", picture=None,
        )
        linked = get_or_create_google_user(
            db_session, google_id=GOOGLE_ID, email=GOOGLE_EMAIL,
            full_name="Old Name", picture=GOOGLE_PICTURE,
        )
        assert linked.id == existing.id
        # The google_id is now attached, linking both sign-in paths.
        assert linked.google_id == GOOGLE_ID
        assert linked.picture == GOOGLE_PICTURE

    def test_updates_profile_when_google_data_changes(self, db_session):
        get_or_create_google_user(
            db_session, google_id=GOOGLE_ID, email=GOOGLE_EMAIL,
            full_name="First Name", picture=None,
        )
        updated = get_or_create_google_user(
            db_session, google_id=GOOGLE_ID, email=GOOGLE_EMAIL,
            full_name="New Name", picture="https://example.com/new.jpg",
        )
        assert updated.full_name == "New Name"
        assert updated.picture == "https://example.com/new.jpg"

    def test_find_by_google_id_prefers_unique_key(self, db_session):
        get_or_create_google_user(
            db_session, google_id=GOOGLE_ID, email=GOOGLE_EMAIL,
            full_name=GOOGLE_NAME, picture=None,
        )
        found = get_or_create_google_user(
            db_session, google_id=GOOGLE_ID, email="other.email@example.com",
            full_name="Renamed", picture=None,
        )
        assert found.email == GOOGLE_EMAIL  # email is not overwritten on lookup

    def test_existing_google_user_with_profile_image_logs_in(self, db_session):
        """A Google user with a local profile_image must be found, not fail.

        Regression test for ``column users.profile_image does not exist``:
        any SELECT on users loads the ``profile_image`` column, so the lookup
        by google_id exercises the fixed schema.
        """
        created = get_or_create_google_user(
            db_session, google_id=GOOGLE_ID, email=GOOGLE_EMAIL,
            full_name=GOOGLE_NAME, picture=GOOGLE_PICTURE,
        )
        created.profile_image = "/uploads/profile/local-avatar.png"
        db_session.commit()

        found = get_or_create_google_user(
            db_session, google_id=GOOGLE_ID, email=GOOGLE_EMAIL,
            full_name=GOOGLE_NAME, picture=GOOGLE_PICTURE,
        )
        assert found.id == created.id
        # The local upload is the canonical profile image; Google sync must
        # only touch ``picture`` and never overwrite it.
        assert found.profile_image == "/uploads/profile/local-avatar.png"
        assert found.picture == GOOGLE_PICTURE

    def test_new_google_user_created_without_undefined_column(self, db_session):
        """A brand-new Google profile (email/google_id/name/picture) is created."""
        user = get_or_create_google_user(
            db_session,
            google_id="new-google-sub-123",
            email="new.google@example.com",
            full_name="New Google",
            picture=GOOGLE_PICTURE,
        )
        assert user.id is not None
        assert user.google_id == "new-google-sub-123"
        assert user.picture == GOOGLE_PICTURE
        # Fresh accounts have no local upload yet — NULL must be supported.
        assert user.profile_image is None


# ---------------------------------------------------------------------------
# Service: login_with_google
# ---------------------------------------------------------------------------


class TestLoginWithGoogle:
    @pytest.mark.anyio
    async def test_creates_user_and_issues_token(self, db_session, monkeypatch):
        async def fake_authenticate(code, redirect_uri=None):  # noqa: ARG001
            return GoogleUserProfile(
                google_id=GOOGLE_ID, email=GOOGLE_EMAIL,
                full_name=GOOGLE_NAME, picture=GOOGLE_PICTURE,
            )

        monkeypatch.setattr(auth_service, "authenticate_with_google", fake_authenticate)
        token = await auth_service.login_with_google(db_session, "real-ish-code")
        assert token.token_type == "bearer"
        user = get_user_by_email(db_session, GOOGLE_EMAIL)
        assert user is not None
        assert int(decode_access_token(token.access_token)["sub"]) == user.id
        assert user.google_id == GOOGLE_ID

    @pytest.mark.anyio
    async def test_links_existing_password_user(self, db_session, monkeypatch):
        get_or_create_google_user(
            db_session, google_id=None, email=GOOGLE_EMAIL,
            full_name="Old Name", picture=None,
        )

        async def fake_authenticate(code, redirect_uri=None):  # noqa: ARG001
            return GoogleUserProfile(
                google_id=GOOGLE_ID, email=GOOGLE_EMAIL,
                full_name=GOOGLE_NAME, picture=GOOGLE_PICTURE,
            )

        monkeypatch.setattr(auth_service, "authenticate_with_google", fake_authenticate)
        token = await auth_service.login_with_google(db_session, "code")
        user = get_user_by_email(db_session, GOOGLE_EMAIL)
        assert user.google_id == GOOGLE_ID
        assert user.picture == GOOGLE_PICTURE
        assert decode_access_token(token.access_token)["sub"] == str(user.id)

    @pytest.mark.anyio
    async def test_google_failure_propagates(self, db_session, monkeypatch):
        async def fail(code, redirect_uri=None):  # noqa: ARG001
            raise GoogleAuthError("Google rejected the sign-in code.")

        monkeypatch.setattr(auth_service, "authenticate_with_google", fail)
        with pytest.raises(GoogleAuthError):
            await auth_service.login_with_google(db_session, "bad-code")

    @pytest.mark.anyio
    async def test_deactivated_user_is_rejected(self, db_session, monkeypatch):
        get_or_create_google_user(
            db_session, google_id=GOOGLE_ID, email=GOOGLE_EMAIL,
            full_name=GOOGLE_NAME, picture=None,
        )
        get_user_by_email(db_session, GOOGLE_EMAIL).is_active = False
        db_session.commit()

        async def fake_authenticate(code, redirect_uri=None):  # noqa: ARG001
            return GoogleUserProfile(
                google_id=GOOGLE_ID, email=GOOGLE_EMAIL,
                full_name=GOOGLE_NAME, picture=None,
            )

        monkeypatch.setattr(auth_service, "authenticate_with_google", fake_authenticate)
        with pytest.raises(ValueError, match="deactivated"):
            await auth_service.login_with_google(db_session, "code")

    @pytest.mark.anyio
    async def test_unverified_google_email_is_rejected(self, db_session, monkeypatch):
        """An unverified Google email must not be used to create/link an account."""

        async def fake_authenticate(code, redirect_uri=None):  # noqa: ARG001
            return GoogleUserProfile(
                google_id=GOOGLE_ID,
                email=GOOGLE_EMAIL,
                full_name=GOOGLE_NAME,
                picture=None,
                email_verified=False,
            )

        monkeypatch.setattr(auth_service, "authenticate_with_google", fake_authenticate)
        with pytest.raises(GoogleAuthError, match="not verified"):
            await auth_service.login_with_google(db_session, "code")
        assert get_user_by_email(db_session, GOOGLE_EMAIL) is None


# ---------------------------------------------------------------------------
# HTTP endpoint: POST /api/auth/google
# ---------------------------------------------------------------------------


class TestGoogleLoginEndpoint:
    def test_returns_access_token(self, client, monkeypatch):
        async def fake_login(db, code, redirect_uri=None, context=None):  # noqa: ARG001
            return Token(access_token="signed-jwt-for-google-user")

        monkeypatch.setattr(auth_service, "login_with_google", fake_login)
        response = client.post("/api/auth/google", json={"code": "auth-code-123"})
        assert response.status_code == 200
        body = response.json()
        assert body["access_token"] == "signed-jwt-for-google-user"
        assert body["token_type"] == "bearer"

    def test_redirect_uri_is_forwarded_to_service(self, client, monkeypatch):
        received: dict = {}

        async def fake_login(db, code, redirect_uri=None, context=None):  # noqa: ARG001
            received["code"] = code
            received["redirect_uri"] = redirect_uri
            return Token(access_token="jwt-for-popup-code")

        monkeypatch.setattr(auth_service, "login_with_google", fake_login)
        response = client.post(
            "/api/auth/google",
            json={"code": "popup-code", "redirect_uri": POSTMESSAGE_REDIRECT_URI},
        )
        assert response.status_code == 200
        assert received["code"] == "popup-code"
        assert received["redirect_uri"] == "postmessage"

    def test_invalid_code_returns_400_with_detail(self, client, monkeypatch):
        async def fail(db, code, redirect_uri=None, context=None):  # noqa: ARG001
            raise GoogleAuthError("Google rejected the sign-in code.")

        monkeypatch.setattr(auth_service, "login_with_google", fail)
        response = client.post("/api/auth/google", json={"code": "expired-code"})
        assert response.status_code == 400
        assert "rejected" in response.json()["detail"]

    def test_unlinked_account_conflict_returns_400(self, client, monkeypatch):
        async def conflict(db, code, redirect_uri=None, context=None):  # noqa: ARG001
            raise ValueError("This Google email is already registered with another account.")

        monkeypatch.setattr(auth_service, "login_with_google", conflict)
        response = client.post("/api/auth/google", json={"code": "auth-code-123"})
        assert response.status_code == 400

    def test_unexpected_failure_returns_500(self, client, monkeypatch):
        async def explode(db, code, redirect_uri=None, context=None):  # noqa: ARG001
            raise RuntimeError("boom")

        monkeypatch.setattr(auth_service, "login_with_google", explode)
        response = client.post("/api/auth/google", json={"code": "auth-code-123"})
        assert response.status_code == 500
        assert "unexpectedly" in response.json()["detail"]

    def test_missing_code_returns_422(self, client):
        assert client.post("/api/auth/google", json={}).status_code == 422

    def test_empty_code_returns_422(self, client):
        assert client.post("/api/auth/google", json={"code": ""}).status_code == 422
