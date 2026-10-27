"""Shared test fixtures and test-database strategy.

How the tests stay away from real data
--------------------------------------
The whole suite runs against a dedicated `resume_analyzer_test` PostgreSQL
database. `DATABASE_URL` is set as an environment variable *before* any app
module is imported, so ``app.core.config`` and ``app.core.database`` connect
to the test database instead of the development/production one.

* The test database is created (if needed) with the same bootstrap helper the
  application uses at startup.
* Tables are created once per session and truncated before every test, which
  makes the tests isolated, repeatable and fast.
"""

import os
import tempfile
from datetime import datetime, timedelta, timezone

# Must happen before importing the app modules below.
os.environ["DATABASE_URL"] = (
    "postgresql://postgres:postgres@localhost:5432/resume_analyzer_test"
)
os.environ["SECRET_KEY"] = "test-secret-key-for-resume-analyzer"
os.environ["SUPERUSER_EMAIL"] = ""
os.environ["SUPERUSER_PASSWORD"] = ""
# Blank the real Resend credentials from backend/.env so the suite never hits
# the live email API, and pin the sender for deterministic mailer assertions.
os.environ["RESEND_API_KEY"] = ""
os.environ["EMAIL_FROM"] = "onboarding@resend.dev"
# Blank the display name / reply-to from backend/.env so mailer assertions on
# the exact `from` value stay deterministic.
os.environ["EMAIL_FROM_NAME"] = ""
os.environ["EMAIL_REPLY_TO"] = ""
# Retry without sleeping during tests; the retry policy itself is exercised by
# tests/test_email.py (which asserts how many times the provider is called).
os.environ["EMAIL_RETRY_BASE_DELAY"] = "0"
# Throwaway Fernet key so custom AI provider keys can be encrypted in tests
# (backend/.env's real key, if any, is never used by the suite).
# Existing tests exercise the platform-fallback provider; the tests for the
# "every HR must configure their own AI" mode switch it on explicitly.
os.environ["REQUIRE_USER_AI_CONFIG"] = "false"
os.environ["AI_CREDENTIAL_ENCRYPTION_KEY"] = "7nDjrhPPT4Ie0rBTPRUQ_AL9V4XYmBv2ygD13uNJx5Q="
# Profile image uploads go to a throwaway directory so tests never write into
# the repository's real uploads folder.
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="resume_analyzer_test_uploads_")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.database import Base, SessionLocal, engine
from app.core.security import create_access_token, decode_access_token, hash_password
from app.core.token_registry import reset_registry
from app.crud import email_verification as email_verification_crud
from app.crud.user import create_user, get_user_by_email
from app.services import auth as auth_service
from app.services import candidate_auth as candidate_auth_service
from app.main import _prepare_schema_and_seed_superuser, _ensure_database, create_app
from app.models import Interview, Job, User, Application  # noqa: F401  (register models)
from app.schemas.user import UserCreate

# Deterministic test data shared across the suite.
TEST_USER_EMAIL = "hr@example.com"
TEST_USER_PASSWORD = "StrongPassword123"
TEST_ADMIN_EMAIL = "admin@example.com"
TEST_ADMIN_PASSWORD = "AdminPass123"

from tests.payloads import JOB_PAYLOAD, APPLICATION_PAYLOAD  # noqa: E402 (shared data)


@pytest.fixture(scope="session", autouse=True)
def _prepare_database():
    """Create the test database (if needed) and all tables once per session."""
    _ensure_database()
    _prepare_schema_and_seed_superuser()
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(autouse=True)
def _clean_tables(_prepare_database):
    """Truncate every table before each test so no data leaks between tests."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE application_responses, application_forms, interviews, "
                "applications, jobs, users, contact_messages, audit_logs, system_errors, "
                "ai_analysis_runs, platform_settings, revoked_tokens, session_cutoffs, "
                "candidate_accounts, application_status_history, email_verifications, "
                "pending_registrations "
                "RESTART IDENTITY CASCADE"
            )
        )
    yield


@pytest.fixture(autouse=True)
def _reset_token_registry(_clean_tables):
    """Clear token revocation state around every test.

    Revocation cutoffs are keyed by user id and the truncation above restarts
    those ids, so a cutoff left behind by one test could otherwise reject a
    token freshly issued to the next one.
    """
    reset_registry()
    auth_service.reset_verification_throttle()
    candidate_auth_service.reset_verification_throttle()
    yield
    reset_registry()
    auth_service.reset_verification_throttle()
    candidate_auth_service.reset_verification_throttle()


@pytest.fixture(autouse=True)
def _mock_resend_email(monkeypatch):
    """Mock outbound email delivery at the service boundary across the test suite."""
    from app.services.email import EmailDeliveryResult

    def fake_send(email: str, token: str, code: str | None = None, path: str = "/verify-email") -> EmailDeliveryResult:
        return EmailDeliveryResult(success=True, message_id="fake_msg_id")

    monkeypatch.setattr("app.services.auth.send_hr_registration_email", fake_send)
    monkeypatch.setattr("app.services.email_verification.send_verification_code_email", lambda e, c: EmailDeliveryResult(success=True, message_id="fake_msg_id"))


@pytest.fixture(scope="session")
def client(_prepare_database):
    """FastAPI TestClient; the app startup runs against the test database."""
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db_session():
    """A plain SQLAlchemy session for direct CRUD/service unit tests."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
# ---------------------------------------------------------------------------
# Authentication fixtures
# ---------------------------------------------------------------------------


def _register(client, email=TEST_USER_EMAIL, full_name="HR User", password=TEST_USER_PASSWORD):
    """Post a registration request and return the raw FastAPI response."""
    return client.post(
        "/api/auth/register",
        json={"email": email, "full_name": full_name, "password": password},
    )


#: Deterministic code the fixtures plant so registration helpers can verify the
#: account through the real endpoint (the emailed code is random and hashed).
TEST_VERIFICATION_CODE = "123456"


def plant_verification_code(db, user_id: int, code: str = TEST_VERIFICATION_CODE) -> None:
    """Invalidate existing codes and store a known one for a user."""
    now = datetime.now(timezone.utc)
    email_verification_crud.invalidate_active(db, user_id, now)
    email_verification_crud.create(
        db,
        user_id=user_id,
        code_hash=hash_password(code),
        expires_at=now + timedelta(minutes=10),
    )


def verify_registered_user(client, response, email):
    """Mark a just-registered HR account's email verified (test helper).

    New registrations are unverified and cannot use panel endpoints. Shared
    fixtures confirm the email through the real endpoint so pre-existing tests
    keep a usable session. A non-201 response (e.g. duplicate email) is
    returned untouched.
    """
    if response.status_code != 201:
        return response
    db = SessionLocal()
    try:
        from app.crud import pending_registration as pending_crud
        pending = pending_crud.get_by_email(db, email)
        if pending is not None:
            pending.code_hash = hash_password(TEST_VERIFICATION_CODE)
            db.commit()
        else:
            user = get_user_by_email(db, email)
            if user is not None:
                plant_verification_code(db, user.id)
    finally:
        db.close()
    verify_res = client.post(
        "/api/auth/verify-email",
        json={"email": email, "code": TEST_VERIFICATION_CODE},
    )
    if verify_res.status_code == 200:
        verify_res.status_code = 201
        return verify_res
    return response


@pytest.fixture
def user_factory(client):
    """Factory that registers a verified user through the API."""

    def _register(email=TEST_USER_EMAIL, full_name="HR User", password=TEST_USER_PASSWORD):
        response = client.post(
            "/api/auth/register",
            json={"email": email, "full_name": full_name, "password": password},
        )
        return verify_registered_user(client, response, email)

    return _register


@pytest.fixture
def user(client):
    """Register a verified HR user and return their id plus Authorization headers."""
    response = verify_registered_user(client, _register(client), TEST_USER_EMAIL)
    assert response.status_code == 201, response.text
    token = response.json()["access_token"]
    user_id = int(decode_access_token(token)["sub"])
    return {"id": user_id, "email": TEST_USER_EMAIL, "headers": {"Authorization": f"Bearer {token}"}}


@pytest.fixture
def other_user(client):
    """Register a second verified HR user (used to test ownership rules)."""
    response = verify_registered_user(
        client, _register(client, email="other@example.com", full_name="Other HR"), "other@example.com"
    )
    assert response.status_code == 201, response.text
    token = response.json()["access_token"]
    user_id = int(decode_access_token(token)["sub"])
    return {
        "id": user_id,
        "email": "other@example.com",
        "headers": {"Authorization": f"Bearer {token}"},
    }


@pytest.fixture
def admin(db_session):
    """Create a superuser directly in the DB (register cannot create admins)."""
    admin_user = create_user(
        db_session,
        UserCreate(
            email=TEST_ADMIN_EMAIL,
            full_name="Administrator",
            password=TEST_ADMIN_PASSWORD,
        ),
        is_superuser=True,
    )
    # Admin endpoints need an admin *session* (the signed role claim), not
    # just the superuser flag, so the fixture signs in to the admin workspace.
    token = create_access_token(subject=admin_user.id, role="admin")
    return {
        "id": admin_user.id,
        "email": TEST_ADMIN_EMAIL,
        "headers": {"Authorization": f"Bearer {token}"},
    }


# ---------------------------------------------------------------------------
# Domain fixtures: jobs and applications
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_job(client, user):
    """Create a job owned by the current HR user and return it plus headers."""
    response = client.post("/api/jobs", json=JOB_PAYLOAD, headers=user["headers"])
    assert response.status_code == 201, response.text
    job = response.json()
    return {"id": job["id"], "data": job, "headers": user["headers"], "owner_id": user["id"]}


@pytest.fixture
def application_factory(client, user):
    """Factory that creates an application for a given job_id."""

    def _create(job_id, payload=None, headers=None):
        response = client.post(
            f"/api/applications?job_id={job_id}",
            json=payload or dict(APPLICATION_PAYLOAD),
            headers=headers or user["headers"],
        )
        return response

    return _create


@pytest.fixture
def sample_application(client, application_factory, sample_job):
    """Create an application attached to ``sample_job`` and return it plus headers."""
    response = application_factory(sample_job["id"])
    assert response.status_code == 201, response.text
    application = response.json()
    return {"id": application["id"], "data": application, "job_id": sample_job["id"], "headers": sample_job["headers"]}