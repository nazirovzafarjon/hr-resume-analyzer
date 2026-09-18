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
# Profile image uploads go to a throwaway directory so tests never write into
# the repository's real uploads folder.
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="resume_analyzer_test_uploads_")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.database import Base, SessionLocal, engine
from app.core.security import create_access_token, decode_access_token
from app.core.token_registry import reset_registry
from app.crud.user import create_user
from app.main import _create_tables_and_seed_superuser, _ensure_database, create_app
from app.models import Interview, Job, User, Worker  # noqa: F401  (register models)
from app.schemas.user import UserCreate

# Deterministic test data shared across the suite.
TEST_USER_EMAIL = "hr@example.com"
TEST_USER_PASSWORD = "StrongPassword123"
TEST_ADMIN_EMAIL = "admin@example.com"
TEST_ADMIN_PASSWORD = "AdminPass123"

from tests.payloads import JOB_PAYLOAD, WORKER_PAYLOAD  # noqa: E402 (shared data)


@pytest.fixture(scope="session", autouse=True)
def _prepare_database():
    """Create the test database (if needed) and all tables once per session."""
    _ensure_database()
    _create_tables_and_seed_superuser()
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
                "workers, jobs, users RESTART IDENTITY CASCADE"
            )
        )
    yield


@pytest.fixture(autouse=True)
def _reset_token_registry(_clean_tables):
    """Clear in-process token revocation state around every test.

    Revocation cutoffs are keyed by user id and the truncation above restarts
    those ids, so a cutoff left behind by one test could otherwise reject a
    token freshly issued to the next one.
    """
    reset_registry()
    yield
    reset_registry()


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


@pytest.fixture
def user_factory(client):
    """Factory that registers a user through the API and returns the response."""

    def _register(email=TEST_USER_EMAIL, full_name="HR User", password=TEST_USER_PASSWORD):
        return client.post(
            "/api/auth/register",
            json={"email": email, "full_name": full_name, "password": password},
        )

    return _register


@pytest.fixture
def user(client):
    """Register an HR user and return their id plus Authorization headers."""
    response = _register(client)
    assert response.status_code == 201, response.text
    token = response.json()["access_token"]
    user_id = int(decode_access_token(token)["sub"])
    return {"id": user_id, "email": TEST_USER_EMAIL, "headers": {"Authorization": f"Bearer {token}"}}


@pytest.fixture
def other_user(client):
    """Register a second HR user (used to test ownership rules)."""
    response = _register(client, email="other@example.com", full_name="Other HR")
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
    token = create_access_token(subject=admin_user.id)
    return {
        "id": admin_user.id,
        "email": TEST_ADMIN_EMAIL,
        "headers": {"Authorization": f"Bearer {token}"},
    }


# ---------------------------------------------------------------------------
# Domain fixtures: jobs and workers
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_job(client, user):
    """Create a job owned by the current HR user and return it plus headers."""
    response = client.post("/api/jobs", json=JOB_PAYLOAD, headers=user["headers"])
    assert response.status_code == 201, response.text
    job = response.json()
    return {"id": job["id"], "data": job, "headers": user["headers"], "owner_id": user["id"]}


@pytest.fixture
def worker_factory(client, user):
    """Factory that creates a worker for a given job_id."""

    def _create(job_id, payload=None, headers=None):
        response = client.post(
            f"/api/workers?job_id={job_id}",
            json=payload or dict(WORKER_PAYLOAD),
            headers=headers or user["headers"],
        )
        return response

    return _create


@pytest.fixture
def sample_worker(client, worker_factory, sample_job):
    """Create a worker attached to ``sample_job`` and return it plus headers."""
    response = worker_factory(sample_job["id"])
    assert response.status_code == 201, response.text
    worker = response.json()
    return {"id": worker["id"], "data": worker, "job_id": sample_job["id"], "headers": sample_job["headers"]}