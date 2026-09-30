"""Tests for session roles: workspace selection at sign-in, switching,
refresh/logout behaviour and that admin endpoints need an admin session."""

from datetime import timedelta

import pytest
from jose import jwt

from app.core.config import settings
from app.core.security import (
    TOKEN_PURPOSE_ROLE_SELECTION,
    _create_token,
    create_access_token,
    create_role_selection_token,
    decode_access_token,
)
from tests.conftest import TEST_ADMIN_EMAIL, TEST_ADMIN_PASSWORD, TEST_USER_PASSWORD

ADMIN_URL = "/api/admin/dashboard"


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _login(client, email, password):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def _select(client, role, selection_token=None, headers=None):
    body = {"role": role}
    if selection_token is not None:
        body["selection_token"] = selection_token
    return client.post("/api/auth/select-role", json=body, headers=headers or {})


@pytest.fixture
def admin_account(admin):
    """The superuser created by the ``admin`` fixture (credentials known)."""
    return admin


@pytest.fixture
def selection(client, admin_account):
    """Sign in as the superuser and return the selection-required body."""
    response = _login(client, TEST_ADMIN_EMAIL, TEST_ADMIN_PASSWORD)
    assert response.status_code == 200, response.text
    return response.json()


def _session(client, role, admin_account):
    body = _login(client, TEST_ADMIN_EMAIL, TEST_ADMIN_PASSWORD).json()
    response = _select(client, role, body["selection_token"])
    assert response.status_code == 200, response.text
    return response.json()


# ---------------------------------------------------------------------------
# Sign-in branching
# ---------------------------------------------------------------------------


class TestSignIn:
    def test_single_role_user_gets_a_session_directly(self, client, user):
        body = _login(client, user["email"], TEST_USER_PASSWORD).json()
        assert body["requires_role_selection"] is False
        assert body["active_role"] == "user"
        assert decode_access_token(body["access_token"])["role"] == "user"
        assert client.get("/api/jobs", headers=_bearer(body["access_token"])).status_code == 200

    def test_registration_is_single_role(self, client, user_factory):
        body = user_factory(email="fresh@example.com").json()
        assert body["requires_role_selection"] is False
        assert body["active_role"] == "user"

    def test_multi_role_user_must_choose(self, selection):
        assert selection["requires_role_selection"] is True
        assert selection["available_roles"] == ["user", "admin"]
        assert selection["full_name"] == "Administrator"
        assert 0 < selection["expires_in"] <= 300
        # No session is handed out before the choice.
        assert "access_token" not in selection
        assert "refresh_token" not in selection

    def test_selection_token_grants_no_api_access(self, client, selection):
        token = selection["selection_token"]
        assert client.get("/api/jobs", headers=_bearer(token)).status_code == 401
        assert client.get(ADMIN_URL, headers=_bearer(token)).status_code == 401
        assert client.get("/api/auth/me", headers=_bearer(token)).status_code == 401
        assert client.post("/api/auth/refresh", json={"refresh_token": token}).status_code == 401

    def test_skip_reset_also_requires_choice(self, client, admin_account):
        from app.core.security import create_password_reset_token

        token = create_password_reset_token(admin_account["id"])
        body = client.post("/api/auth/skip-reset", json={"token": token}).json()
        assert body["requires_role_selection"] is True


# ---------------------------------------------------------------------------
# Choosing a workspace
# ---------------------------------------------------------------------------


class TestSelectRole:
    def test_choose_hr_workspace(self, client, selection):
        response = _select(client, "user", selection["selection_token"])
        assert response.status_code == 200
        body = response.json()
        assert body["active_role"] == "user"
        headers = _bearer(body["access_token"])
        assert client.get("/api/jobs", headers=headers).status_code == 200
        me = client.get("/api/auth/me", headers=headers).json()
        assert me["active_role"] == "user"
        assert me["available_roles"] == ["user", "admin"]

    def test_hr_session_of_superuser_cannot_use_admin_endpoints(self, client, selection):
        body = _select(client, "user", selection["selection_token"]).json()
        headers = _bearer(body["access_token"])
        for path in (ADMIN_URL, "/api/admin/users", "/api/users"):
            response = client.get(path, headers=headers)
            assert response.status_code == 403, path
        assert "admin workspace" in client.get(ADMIN_URL, headers=headers).json()["detail"]

    def test_choose_admin_workspace(self, client, selection):
        body = _select(client, "admin", selection["selection_token"]).json()
        assert body["active_role"] == "admin"
        headers = _bearer(body["access_token"])
        assert client.get(ADMIN_URL, headers=headers).status_code == 200
        # HR endpoints keep working for the user's own data.
        assert client.get("/api/jobs", headers=headers).status_code == 200

    def test_selection_token_is_single_use(self, client, selection):
        assert _select(client, "user", selection["selection_token"]).status_code == 200
        replay = _select(client, "admin", selection["selection_token"])
        assert replay.status_code == 401

    def test_invalid_role_rejected(self, client, selection):
        assert _select(client, "superadmin", selection["selection_token"]).status_code == 422
        assert _select(client, "", selection["selection_token"]).status_code == 422

    def test_hr_user_cannot_select_admin(self, client, user, db_session):
        token = create_role_selection_token(user["id"])
        response = _select(client, "admin", token)
        assert response.status_code == 403
        assert response.json()["detail"] == "This workspace is not available for your account."

    def test_hr_user_cannot_switch_to_admin(self, client, user):
        response = _select(client, "admin", headers=user["headers"])
        assert response.status_code == 403
        assert client.get(ADMIN_URL, headers=user["headers"]).status_code == 403

    def test_expired_selection_token(self, client, admin_account):
        expired = _create_token(
            admin_account["id"], timedelta(seconds=-1), TOKEN_PURPOSE_ROLE_SELECTION
        )
        assert _select(client, "admin", expired).status_code == 401

    def test_access_token_is_not_a_selection_token(self, client, user):
        token = user["headers"]["Authorization"].split()[1]
        assert _select(client, "user", token).status_code == 401

    def test_forged_or_tampered_tokens(self, client, admin_account, user):
        # Signed with the wrong key.
        forged = jwt.encode(
            {"sub": str(user["id"]), "typ": "access", "role": "admin"}, "wrong-key", algorithm="HS256"
        )
        assert client.get(ADMIN_URL, headers=_bearer(forged)).status_code == 401
        # Correctly signed admin claim, but the account is not a superuser.
        claimed = create_access_token(user["id"], role="admin")
        assert client.get(ADMIN_URL, headers=_bearer(claimed)).status_code == 403
        # Payload edited without re-signing.
        good = create_access_token(admin_account["id"], role="user")
        header, _payload, signature = good.split(".")
        import base64
        import json

        edited = base64.urlsafe_b64encode(
            json.dumps({"sub": str(admin_account["id"]), "typ": "access", "role": "admin"}).encode()
        ).decode().rstrip("=")
        assert client.get(ADMIN_URL, headers=_bearer(f"{header}.{edited}.{signature}")).status_code == 401

    def test_request_manipulation_is_ignored(self, client, user):
        # Query strings and unknown body fields confer nothing.
        headers = user["headers"]
        assert client.get(f"{ADMIN_URL}?role=admin&is_superuser=true", headers=headers).status_code == 403
        response = client.patch(
            "/api/auth/me", json={"is_superuser": True, "role": "admin"}, headers=headers
        )
        assert response.status_code == 200
        assert client.get("/api/auth/me", headers=headers).json()["is_superuser"] is False
        assert client.get(ADMIN_URL, headers=headers).status_code == 403
        # Users cannot promote themselves through the admin API either.
        assert client.put(
            f"/api/users/{user['id']}", json={"is_superuser": True}, headers=headers
        ).status_code == 403

    def test_inactive_account_cannot_select(self, client, selection, admin_account, db_session):
        from app.crud import user as user_crud
        from app.schemas.user import UserCreate

        # Keep another admin so the account can be deactivated directly.
        user_crud.create_user(
            db_session,
            UserCreate(email="second@example.com", full_name="Second", password="Pass12345"),
            is_superuser=True,
        )
        account = user_crud.get_user_by_id(db_session, admin_account["id"])
        user_crud.update_user(db_session, account, {"is_active": False})
        assert _select(client, "admin", selection["selection_token"]).status_code == 401
        assert _login(client, TEST_ADMIN_EMAIL, TEST_ADMIN_PASSWORD).status_code == 401

    def test_role_events_are_audited(self, client, selection):
        admin_body = _select(client, "admin", selection["selection_token"]).json()
        headers = _bearer(admin_body["access_token"])
        logs = client.get("/api/admin/audit-logs?action=ROLE_SELECTED", headers=headers).json()
        entry = logs["items"][0]
        assert entry["details"] == {"role": "admin"}
        assert entry["request_id"]
        assert selection["selection_token"] not in str(logs)


# ---------------------------------------------------------------------------
# Switching, refresh and logout
# ---------------------------------------------------------------------------


class TestSessionLifecycle:
    def test_switch_workspace(self, client, admin_account):
        hr = _session(client, "user", admin_account)
        old_headers = _bearer(hr["access_token"])
        switched = _select(client, "admin", headers=old_headers)
        assert switched.status_code == 200
        body = switched.json()
        assert body["active_role"] == "admin"
        assert client.get(ADMIN_URL, headers=_bearer(body["access_token"])).status_code == 200
        # The previous session token stops working.
        assert client.get("/api/jobs", headers=old_headers).status_code == 401

        back = _select(client, "user", headers=_bearer(body["access_token"])).json()
        assert client.get(ADMIN_URL, headers=_bearer(back["access_token"])).status_code == 403

        logs = client.get(
            "/api/admin/audit-logs?action=ROLE_SWITCHED",
            headers=_bearer(_session(client, "admin", admin_account)["access_token"]),
        ).json()
        assert {"role": "admin", "from_role": "user"} in [e["details"] for e in logs["items"]]

    def test_switch_requires_a_session(self, client):
        assert _select(client, "user").status_code == 401

    @pytest.mark.parametrize("role", ["user", "admin"])
    def test_refresh_preserves_role(self, client, admin_account, role):
        session = _session(client, role, admin_account)
        refreshed = client.post("/api/auth/refresh", json={"refresh_token": session["refresh_token"]})
        assert refreshed.status_code == 200
        body = refreshed.json()
        assert body["active_role"] == role
        assert decode_access_token(body["access_token"])["role"] == role
        status = client.get(ADMIN_URL, headers=_bearer(body["access_token"])).status_code
        assert status == (200 if role == "admin" else 403)

    def test_refresh_downgrades_after_demotion(self, client, admin_account, db_session):
        from app.crud import user as user_crud
        from app.schemas.user import UserCreate

        session = _session(client, "admin", admin_account)
        user_crud.create_user(
            db_session,
            UserCreate(email="second@example.com", full_name="Second", password="Pass12345"),
            is_superuser=True,
        )
        account = user_crud.get_user_by_id(db_session, admin_account["id"])
        user_crud.update_user(db_session, account, {"is_superuser": False})
        # Existing admin token: capability is re-checked on every request.
        assert client.get(ADMIN_URL, headers=_bearer(session["access_token"])).status_code == 403
        body = client.post(
            "/api/auth/refresh", json={"refresh_token": session["refresh_token"]}
        ).json()
        assert body["active_role"] == "user"

    def test_legacy_token_without_role_is_hr(self, client, admin_account):
        legacy = create_access_token(admin_account["id"])  # no role claim
        assert client.get(ADMIN_URL, headers=_bearer(legacy)).status_code == 403
        assert client.get("/api/jobs", headers=_bearer(legacy)).status_code == 200

    def test_logout_revokes_session_and_requires_choice_again(self, client, admin_account):
        session = _session(client, "admin", admin_account)
        headers = _bearer(session["access_token"])
        response = client.post(
            "/api/auth/logout", json={"refresh_token": session["refresh_token"]}, headers=headers
        )
        assert response.status_code == 204
        assert client.get(ADMIN_URL, headers=headers).status_code == 401
        assert client.post(
            "/api/auth/refresh", json={"refresh_token": session["refresh_token"]}
        ).status_code == 401
        # Signing in again asks for the workspace again (no silent admin).
        again = _login(client, TEST_ADMIN_EMAIL, TEST_ADMIN_PASSWORD).json()
        assert again["requires_role_selection"] is True

    def test_logout_ignores_foreign_refresh_token(self, client, user, other_user):
        from app.services.auth import issue_token
        from app.crud.user import get_user_by_id
        from app.core.database import SessionLocal

        db = SessionLocal()
        other_refresh = issue_token(get_user_by_id(db, other_user["id"])).refresh_token
        db.close()
        client.post("/api/auth/logout", json={"refresh_token": other_refresh}, headers=user["headers"])
        # The other user's refresh token still works.
        assert client.post("/api/auth/refresh", json={"refresh_token": other_refresh}).status_code == 200

    def test_password_change_keeps_workspace(self, client, admin_account):
        session = _session(client, "admin", admin_account)
        response = client.patch(
            "/api/auth/me/password",
            json={"current_password": TEST_ADMIN_PASSWORD, "new_password": "NewAdminPass456"},
            headers=_bearer(session["access_token"]),
        )
        assert response.status_code == 200
        assert response.json()["active_role"] == "admin"
