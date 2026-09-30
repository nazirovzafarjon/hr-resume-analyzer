"""Tests for the SUPERUSER_* startup setting (ensure_configured_superuser)."""

from app.core.security import verify_password
from app.crud import user as user_crud
from app.models.audit_log import AuditLog
from app.schemas.user import UserCreate
from app.services.user_admin import ensure_configured_superuser


def _actions(db, user_id):
    return [row.action for row in db.query(AuditLog).filter(AuditLog.resource_id == str(user_id))]


def test_creates_missing_account(db_session):
    user = ensure_configured_superuser(
        db_session, email="Boss@Example.com", password="StrongPass123", full_name="Boss"
    )
    assert user is not None
    assert user.email == "boss@example.com"
    assert user.is_superuser and user.is_active
    assert verify_password("StrongPass123", user.hashed_password)
    assert "REGISTER" in _actions(db_session, user.id)


def test_missing_account_without_password_is_not_created(db_session):
    assert ensure_configured_superuser(db_session, email="nobody@example.com", password="") is None
    assert ensure_configured_superuser(db_session, email="nobody@example.com", password="short") is None
    assert user_crud.get_user_by_email(db_session, "nobody@example.com") is None


def test_promotes_and_reactivates_existing_account(db_session):
    user = user_crud.create_user(
        db_session, UserCreate(email="hr@example.com", full_name="HR", password="OriginalPass1")
    )
    user_crud.update_user(db_session, user, {"is_active": False})
    ensure_configured_superuser(db_session, email="hr@example.com", password="OtherPass123")
    db_session.refresh(user)
    assert user.is_superuser and user.is_active
    # An existing password is never overwritten by the environment.
    assert verify_password("OriginalPass1", user.hashed_password)
    assert {"PROMOTE_USER", "ACTIVATE_USER"} <= set(_actions(db_session, user.id))


def test_sets_password_for_google_only_account(db_session):
    user = user_crud.get_or_create_google_user(
        db_session, google_id="g-1", email="google@example.com", full_name="G", picture=None
    )
    assert user.hashed_password is None
    ensure_configured_superuser(db_session, email="google@example.com", password="GoogleAdmin123")
    db_session.refresh(user)
    assert user.is_superuser
    assert verify_password("GoogleAdmin123", user.hashed_password)


def test_is_idempotent_and_leaves_other_accounts_alone(db_session):
    other = user_crud.create_user(
        db_session, UserCreate(email="other@example.com", full_name="O", password="OtherPass123")
    )
    ensure_configured_superuser(db_session, email="boss@example.com", password="StrongPass123")
    ensure_configured_superuser(db_session, email="boss@example.com", password="StrongPass123")
    boss = user_crud.get_user_by_email(db_session, "boss@example.com")
    assert _actions(db_session, boss.id).count("REGISTER") == 1
    db_session.refresh(other)
    assert other.is_superuser is False


def test_configured_admin_can_sign_in_and_choose_admin(client, db_session):
    ensure_configured_superuser(db_session, email="boss@example.com", password="StrongPass123")
    body = client.post(
        "/api/auth/login", json={"email": "boss@example.com", "password": "StrongPass123"}
    ).json()
    assert body["requires_role_selection"] is True
    session = client.post(
        "/api/auth/select-role", json={"role": "admin", "selection_token": body["selection_token"]}
    ).json()
    headers = {"Authorization": f"Bearer {session['access_token']}"}
    assert client.get("/api/admin/dashboard", headers=headers).status_code == 200
