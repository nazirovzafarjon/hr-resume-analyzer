"""Tests for the database-backed token revocation registry.

The registry used to live in process memory; these tests pin down that the
state is now in PostgreSQL, so it survives restarts and is shared by workers.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core import token_registry
from app.core.database import SessionLocal
from app.models.token_revocation import RevokedToken, SessionCutoff
from tests.conftest import TEST_USER_PASSWORD


def _now() -> datetime:
    return datetime.now(timezone.utc)


def test_revoked_token_is_stored_in_the_database(db_session):
    token_registry.revoke_token("jti-abc", expires_at=_now() + timedelta(hours=1))
    assert db_session.get(RevokedToken, "jti-abc") is not None
    # A different connection (another worker, or the API after a restart)
    # sees the same revocation.
    other = SessionLocal()
    try:
        assert token_registry.is_token_revoked("jti-abc", db=other)
    finally:
        other.close()
    assert not token_registry.is_token_revoked("jti-unknown")
    assert not token_registry.is_token_revoked(None)


def test_revoking_twice_is_harmless():
    expiry = _now() + timedelta(hours=1)
    token_registry.revoke_token("jti-dup", expires_at=expiry)
    token_registry.revoke_token("jti-dup", expires_at=expiry)
    assert token_registry.is_token_revoked("jti-dup")


def test_expired_entries_are_pruned(db_session):
    token_registry.revoke_token("jti-old", expires_at=_now() - timedelta(minutes=1))
    # The next write prunes rows whose token has expired anyway.
    token_registry.revoke_token("jti-new", expires_at=_now() + timedelta(hours=1))
    db_session.expire_all()
    remaining = set(db_session.execute(select(RevokedToken.jti)).scalars())
    assert remaining == {"jti-new"}


def test_session_cutoff_is_persistent_and_monotonic(user, db_session):
    later = token_registry.revoke_sessions_before(user["id"], when=_now() + timedelta(hours=1))
    earlier = token_registry.revoke_sessions_before(user["id"], when=_now())
    # An older cutoff never un-revokes anything.
    assert earlier == later
    stored = db_session.get(SessionCutoff, user["id"])
    assert stored is not None and stored.cutoff == later
    assert token_registry.is_session_revoked(user["id"], _now())
    assert not token_registry.is_session_revoked(user["id"], later + timedelta(seconds=1))


def test_cutoff_is_deleted_with_the_user(admin, user, client, db_session):
    token_registry.revoke_sessions_before(user["id"])
    assert client.delete(f"/api/users/{user['id']}", headers=admin["headers"]).status_code == 204
    db_session.expire_all()
    assert db_session.get(SessionCutoff, user["id"]) is None


def test_logout_revocation_survives_a_restart(client, user):
    """Simulate a restart: a brand-new app instance still rejects the token."""
    from fastapi.testclient import TestClient

    from app.main import create_app

    login = client.post(
        "/api/auth/login", json={"email": user["email"], "password": TEST_USER_PASSWORD}
    ).json()
    headers = {"Authorization": f"Bearer {login['access_token']}"}
    client.post("/api/auth/logout", json={"refresh_token": login["refresh_token"]}, headers=headers)

    with TestClient(create_app()) as restarted:
        assert restarted.get("/api/jobs", headers=headers).status_code == 401
        assert restarted.post(
            "/api/auth/refresh", json={"refresh_token": login["refresh_token"]}
        ).status_code == 401


def test_password_change_revocation_survives_a_restart(client, user):
    from fastapi.testclient import TestClient

    from app.main import create_app

    old_headers = user["headers"]
    response = client.patch(
        "/api/auth/me/password",
        json={"current_password": TEST_USER_PASSWORD, "new_password": "BrandNewPass456"},
        headers=old_headers,
    )
    assert response.status_code == 200
    with TestClient(create_app()) as restarted:
        assert restarted.get("/api/jobs", headers=old_headers).status_code == 401
        new_headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
        assert restarted.get("/api/jobs", headers=new_headers).status_code == 200
