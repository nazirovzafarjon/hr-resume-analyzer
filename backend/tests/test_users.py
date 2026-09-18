"""Tests for superuser user management endpoints and user CRUD functions.

The ``/api/users`` endpoints are superuser-only: a normal HR user gets 403,
an anonymous request gets 401.
"""

import pytest

from app.crud import user as user_crud
from app.schemas.user import UserCreate


# ---------------------------------------------------------------------------
# Endpoint tests
# ---------------------------------------------------------------------------


class TestListUsers:
    def test_admin_lists_all_users(self, client, admin, user_factory):
        user_factory()  # one regular HR user
        response = client.get("/api/users", headers=admin["headers"])
        assert response.status_code == 200
        emails = [item["email"] for item in response.json()]
        assert "hr@example.com" in emails
        assert "admin@example.com" in emails

    def test_list_users_pagination(self, client, admin, user_factory):
        user_factory(email="one@example.com")
        user_factory(email="two@example.com")
        response = client.get("/api/users?skip=0&limit=1", headers=admin["headers"])
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_list_users_as_regular_user_forbidden(self, client, user):
        response = client.get("/api/users", headers=user["headers"])
        assert response.status_code == 403

    def test_list_users_without_token(self, client):
        assert client.get("/api/users").status_code == 401

    def test_list_users_invalid_pagination(self, client, admin):
        assert client.get("/api/users?limit=0", headers=admin["headers"]).status_code == 422


class TestGetUser:
    def test_admin_gets_user_by_id(self, client, admin, user_factory, db_session):
        user_factory()
        user = user_crud.get_user_by_email(db_session, "hr@example.com")
        response = client.get(f"/api/users/{user.id}", headers=admin["headers"])
        assert response.status_code == 200
        assert response.json()["email"] == "hr@example.com"
        # The password hash must never be exposed.
        assert "hashed_password" not in response.json()

    def test_get_missing_user_returns_404(self, client, admin):
        response = client.get("/api/users/999999", headers=admin["headers"])
        assert response.status_code == 404
class TestUpdateUser:
    def test_admin_updates_full_name(self, client, admin, user_factory, db_session):
        user_factory()
        target = user_crud.get_user_by_email(db_session, "hr@example.com")
        response = client.put(
            f"/api/users/{target.id}",
            json={"full_name": "New Name"},
            headers=admin["headers"],
        )
        assert response.status_code == 200
        assert response.json()["full_name"] == "New Name"

    def test_admin_deactivates_and_reactivates_user(self, client, admin, user_factory, db_session):
        user_factory()
        target = user_crud.get_user_by_email(db_session, "hr@example.com")
        response = client.put(
            f"/api/users/{target.id}", json={"is_active": False}, headers=admin["headers"]
        )
        assert response.status_code == 200
        assert response.json()["is_active"] is False

        response = client.put(
            f"/api/users/{target.id}", json={"is_active": True}, headers=admin["headers"]
        )
        assert response.status_code == 200
        assert response.json()["is_active"] is True

    def test_update_missing_user_returns_404(self, client, admin):
        response = client.put("/api/users/999999", json={"full_name": "X"}, headers=admin["headers"])
        assert response.status_code == 404

    def test_update_as_regular_user_forbidden(self, client, user, admin):
        response = client.put(f"/api/users/{admin['id']}", json={"full_name": "X"}, headers=user["headers"])
        assert response.status_code == 403

    def test_admin_cannot_demote_own_account(self, client, admin):
        response = client.put(
            f"/api/users/{admin['id']}",
            json={"is_superuser": False},
            headers=admin["headers"],
        )
        assert response.status_code == 400

    def test_admin_cannot_deactivate_own_account(self, client, admin):
        response = client.put(
            f"/api/users/{admin['id']}",
            json={"is_active": False},
            headers=admin["headers"],
        )
        assert response.status_code == 400


class TestDeleteUser:
    def test_admin_deletes_user(self, client, admin, user_factory, db_session):
        user_factory()
        target = user_crud.get_user_by_email(db_session, "hr@example.com")
        target_id = target.id
        response = client.delete(f"/api/users/{target_id}", headers=admin["headers"])
        assert response.status_code == 204
        # Query-based check: querying by email always hits the DB, so the
        # row being gone is a reliable assertion (unlike the identity map).
        assert user_crud.get_user_by_email(db_session, "hr@example.com") is None

    def test_delete_user_removes_their_jobs_and_workers(
        self, client, admin, db_session, sample_job, worker_factory
    ):
        worker_response = worker_factory(sample_job["id"])  # hr@example.com owns a job with a worker
        worker_id = worker_response.json()["id"]
        job_id = sample_job["id"]
        target = user_crud.get_user_by_email(db_session, "hr@example.com")
        target_id = target.id

        assert client.delete(f"/api/users/{target_id}", headers=admin["headers"]).status_code == 204

        # Query-based checks: each lookup hits the DB, so deleted rows return
        # None reliably (unlike lookups through the session identity map).
        from app.crud.job import get_job
        from app.crud.worker import get_worker

        assert user_crud.get_user_by_email(db_session, "hr@example.com") is None
        assert get_job(db_session, job_id) is None
        assert get_worker(db_session, worker_id) is None

    def test_admin_cannot_delete_own_account(self, client, admin):
        response = client.delete(f"/api/users/{admin['id']}", headers=admin["headers"])
        assert response.status_code == 400

    def test_delete_missing_user_returns_404(self, client, admin):
        assert client.delete("/api/users/999999", headers=admin["headers"]).status_code == 404
# ---------------------------------------------------------------------------
# User CRUD functions
# ---------------------------------------------------------------------------


class TestUserCrud:
    def test_create_user(self, db_session):
        user = user_crud.create_user(
            db_session, UserCreate(email="crud@example.com", full_name="CRUD User", password="CrudPass123")
        )
        assert user.id is not None
        assert user.email == "crud@example.com"
        assert user.is_superuser is False
        assert user.hashed_password.startswith("$2b$")

    def test_create_user_with_duplicate_email_raises(self, db_session):
        payload = UserCreate(email="crud@example.com", full_name="First", password="CrudPass123")
        user_crud.create_user(db_session, payload)
        with pytest.raises(ValueError):
            user_crud.create_user(db_session, payload)

    def test_list_users_with_pagination(self, db_session):
        for i in range(3):
            user_crud.create_user(
                db_session,
                UserCreate(email=f"user{i}@example.com", full_name=f"User {i}", password="CrudPass123"),
            )
        users = user_crud.list_users(db_session, skip=1, limit=1)
        assert len(users) == 1
        assert users[0].email == "user1@example.com"

    def test_get_user_by_id(self, db_session):
        user = user_crud.create_user(
            db_session, UserCreate(email="crud@example.com", full_name="CRUD User", password="CrudPass123")
        )
        assert user_crud.get_user_by_id(db_session, user.id) is user
        assert user_crud.get_user_by_id(db_session, 999999) is None

    def test_get_user_by_email(self, db_session):
        user_crud.create_user(
            db_session, UserCreate(email="crud@example.com", full_name="CRUD User", password="CrudPass123")
        )
        found = user_crud.get_user_by_email(db_session, "crud@example.com")
        assert found is not None and found.email == "crud@example.com"
        assert user_crud.get_user_by_email(db_session, "missing@example.com") is None

    def test_update_user_applies_only_present_fields(self, db_session):
        user = user_crud.create_user(
            db_session, UserCreate(email="crud@example.com", full_name="Old Name", password="CrudPass123")
        )
        updated = user_crud.update_user(db_session, user, {"full_name": "New Name"})
        assert updated.full_name == "New Name"
        assert updated.email == "crud@example.com"  # untouched
        assert updated.is_active is True

    def test_delete_user(self, db_session):
        user = user_crud.create_user(
            db_session, UserCreate(email="crud@example.com", full_name="CRUD User", password="CrudPass123")
        )
        user_crud.delete_user(db_session, user)
        assert user_crud.get_user_by_id(db_session, user.id) is None

    def test_count_users(self, db_session):
        assert user_crud.count_users(db_session) == 0
        user_crud.create_user(
            db_session, UserCreate(email="crud@example.com", full_name="CRUD User", password="CrudPass123")
        )
        assert user_crud.count_users(db_session) == 1

    def test_has_superuser(self, db_session):
        assert user_crud.has_superuser(db_session) is False
        user_crud.create_user(
            db_session,
            UserCreate(email="admin@example.com", full_name="Admin", password="AdminPass123"),
            is_superuser=True,
        )
        assert user_crud.has_superuser(db_session) is True