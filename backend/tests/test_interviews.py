"""Tests for interview endpoints and interview CRUD functions.

Interviews are scoped to the authenticated HR user (``hr_id``): other users'
interviews behave like "not found", and a candidate must belong to a job owned
by the caller before an interview can be created against it.
"""

from tests.payloads import INTERVIEW_PAYLOAD, JOB_PAYLOAD, WORKER_PAYLOAD

from app.crud import interview as interview_crud
from app.crud import job as job_crud
from app.crud import worker as worker_crud
from app.models.interview import InterviewStatus
from app.schemas.interview import InterviewCreate, InterviewUpdate
from app.schemas.job import JobCreate
from app.schemas.worker import WorkerCreate


def _create_interview(client, headers, candidate_id, **overrides):
    """Create an interview through the API; returns the raw response."""
    payload = {**INTERVIEW_PAYLOAD, "candidate_id": candidate_id, **overrides}
    return client.post("/api/interviews", json=payload, headers=headers)


def _create_owner(db_session, email="owner@example.com"):
    """Create a user row directly so FKs are satisfied in CRUD tests."""
    from app.crud import user as user_crud
    from app.schemas.user import UserCreate

    return user_crud.create_user(
        db_session, UserCreate(email=email, full_name="Owner", password="PassPass123")
    )


def _create_job_with_owner(db_session, owner_id, position="Backend Developer"):
    """Create a job row directly so workers have a valid owner."""
    return job_crud.create_job(
        db_session,
        owner_id=owner_id,
        payload=JobCreate(**{**JOB_PAYLOAD, "position": position}),
    )


def _create_worker(db_session, job_id):
    """Create a worker row directly for CRUD tests."""
    return worker_crud.create_worker(
        db_session, job_id=job_id, payload=WorkerCreate(**WORKER_PAYLOAD)
    )


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


class TestCreateInterview:
    def test_create_interview_success(self, client, sample_worker):
        response = _create_interview(client, sample_worker["headers"], sample_worker["id"])
        assert response.status_code == 201
        body = response.json()
        assert body["interviewer"] == "Anna HR"
        assert body["candidate_id"] == sample_worker["id"]
        assert body["status"] == "upcoming"
        assert body["meeting_link"] == "https://meet.example.com/round-1"
        assert body["id"] > 0
        # Candidate/job context is enriched on the response.
        assert body["candidate_name"] == "Jane Doe"
        assert body["job_title"] == "Backend Developer"
        assert body["company_name"] == "Acme Corp"

    def test_create_interview_persists_owner(self, client, sample_worker, sample_job, db_session):
        response = _create_interview(client, sample_worker["headers"], sample_worker["id"])
        interview = interview_crud.get_interview_by_id(
            db_session, response.json()["id"], sample_job["owner_id"]
        )
        assert interview is not None
        assert interview.hr_id == sample_job["owner_id"]

    def test_create_interview_default_status(self, client, sample_worker):
        response = client.post(
            "/api/interviews",
            json={**INTERVIEW_PAYLOAD, "candidate_id": sample_worker["id"]},
            headers=sample_worker["headers"],
        )
        assert response.status_code == 201
        assert response.json()["status"] == "upcoming"

    def test_create_interview_for_unowned_candidate_returns_404(self, client, sample_worker, other_user):
        response = _create_interview(client, other_user["headers"], sample_worker["id"])
        assert response.status_code == 404

    def test_create_interview_missing_candidate_returns_404(self, client, user):
        response = _create_interview(client, user["headers"], 999999)
        assert response.status_code == 404

    def test_create_interview_requires_auth(self, client, sample_worker):
        response = client.post(
            "/api/interviews",
            json={**INTERVIEW_PAYLOAD, "candidate_id": sample_worker["id"]},
        )
        assert response.status_code == 401

    def test_create_interview_missing_required_fields(self, client, sample_worker):
        payload = {**INTERVIEW_PAYLOAD, "candidate_id": sample_worker["id"]}
        payload.pop("interviewer")
        response = client.post("/api/interviews", json=payload, headers=sample_worker["headers"])
        assert response.status_code == 422

    def test_create_interview_empty_interviewer(self, client, sample_worker):
        response = _create_interview(
            client, sample_worker["headers"], sample_worker["id"], interviewer=""
        )
        assert response.status_code == 422
# ---------------------------------------------------------------------------
# Read / list
# ---------------------------------------------------------------------------


class TestListInterviews:
    def test_list_interviews_returns_own(self, client, sample_worker):
        _create_interview(client, sample_worker["headers"], sample_worker["id"])
        _create_interview(
            client,
            sample_worker["headers"],
            sample_worker["id"],
            interviewer="Peter Frontend",
        )
        response = client.get("/api/interviews", headers=sample_worker["headers"])
        assert response.status_code == 200
        assert {row["interviewer"] for row in response.json()} == {"Anna HR", "Peter Frontend"}

    def test_list_interviews_excludes_other_users(self, client, sample_worker, other_user):
        _create_interview(client, sample_worker["headers"], sample_worker["id"])
        response = client.get("/api/interviews", headers=other_user["headers"])
        assert response.status_code == 200
        assert response.json() == []

    def test_list_interviews_filters_by_status(self, client, sample_worker):
        _create_interview(client, sample_worker["headers"], sample_worker["id"])
        _create_interview(
            client,
            sample_worker["headers"],
            sample_worker["id"],
            interviewer="Completed Interviewer",
            status="completed",
        )
        response = client.get(
            "/api/interviews?status=completed", headers=sample_worker["headers"]
        )
        assert response.status_code == 200
        rows = response.json()
        assert len(rows) == 1
        assert rows[0]["interviewer"] == "Completed Interviewer"

    def test_list_interviews_searches_by_candidate_name(self, client, sample_worker):
        _create_interview(client, sample_worker["headers"], sample_worker["id"])
        response = client.get(
            "/api/interviews?search=jane", headers=sample_worker["headers"]
        )
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_list_interviews_searches_by_interviewer(self, client, sample_worker):
        _create_interview(client, sample_worker["headers"], sample_worker["id"])
        response = client.get(
            "/api/interviews?search=anna", headers=sample_worker["headers"]
        )
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_list_interviews_search_miss_returns_empty(self, client, sample_worker):
        _create_interview(client, sample_worker["headers"], sample_worker["id"])
        response = client.get(
            "/api/interviews?search=zzz", headers=sample_worker["headers"]
        )
        assert response.json() == []

    def test_list_interviews_requires_auth(self, client):
        assert client.get("/api/interviews").status_code == 401


class TestGetInterview:
    def test_get_own_interview(self, client, sample_worker):
        created = _create_interview(client, sample_worker["headers"], sample_worker["id"]).json()
        response = client.get(f"/api/interviews/{created['id']}", headers=sample_worker["headers"])
        assert response.status_code == 200
        assert response.json()["id"] == created["id"]
        assert response.json()["candidate_name"] == "Jane Doe"

    def test_get_other_users_interview_is_not_found(self, client, sample_worker, other_user):
        created = _create_interview(client, sample_worker["headers"], sample_worker["id"]).json()
        response = client.get(f"/api/interviews/{created['id']}", headers=other_user["headers"])
        assert response.status_code == 404

    def test_get_missing_interview_returns_404(self, client, user):
        assert client.get("/api/interviews/999999", headers=user["headers"]).status_code == 404
# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


class TestUpdateInterview:
    def test_patch_updates_status_and_fields(self, client, sample_worker):
        created = _create_interview(client, sample_worker["headers"], sample_worker["id"]).json()
        response = client.patch(
            f"/api/interviews/{created['id']}",
            json={"status": "completed", "notes": "Done — strong hire.", "meeting_link": None},
            headers=sample_worker["headers"],
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "completed"
        assert body["notes"] == "Done — strong hire."
        assert body["meeting_link"] is None
        # Untouched fields stay unchanged.
        assert body["interviewer"] == "Anna HR"

    def test_patch_other_users_interview_is_not_found(self, client, sample_worker, other_user):
        created = _create_interview(client, sample_worker["headers"], sample_worker["id"]).json()
        response = client.patch(
            f"/api/interviews/{created['id']}",
            json={"status": "cancelled"},
            headers=other_user["headers"],
        )
        assert response.status_code == 404

    def test_patch_to_unowned_candidate_returns_404(self, client, sample_worker, other_user):
        created = _create_interview(client, sample_worker["headers"], sample_worker["id"]).json()
        # Another user's candidate cannot be assigned to this interview.
        other_job = client.post("/api/jobs", json=JOB_PAYLOAD, headers=other_user["headers"])
        assert other_job.status_code == 201
        other_worker = client.post(
            f"/api/workers?job_id={other_job.json()['id']}",
            json=WORKER_PAYLOAD,
            headers=other_user["headers"],
        )
        assert other_worker.status_code == 201
        response = client.patch(
            f"/api/interviews/{created['id']}",
            json={"candidate_id": other_worker.json()["id"]},
            headers=sample_worker["headers"],
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


class TestDeleteInterview:
    def test_delete_own_interview(self, client, sample_worker):
        created = _create_interview(client, sample_worker["headers"], sample_worker["id"]).json()
        response = client.delete(f"/api/interviews/{created['id']}", headers=sample_worker["headers"])
        assert response.status_code == 204
        get_response = client.get(
            f"/api/interviews/{created['id']}", headers=sample_worker["headers"]
        )
        assert get_response.status_code == 404

    def test_delete_other_users_interview_is_not_found(self, client, sample_worker, other_user):
        created = _create_interview(client, sample_worker["headers"], sample_worker["id"]).json()
        response = client.delete(
            f"/api/interviews/{created['id']}", headers=other_user["headers"]
        )
        assert response.status_code == 404

    def test_delete_missing_interview_returns_404(self, client, user):
        assert client.delete("/api/interviews/999999", headers=user["headers"]).status_code == 404
# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


class TestInterviewStats:
    def test_stats_counts(self, client, sample_worker):
        _create_interview(client, sample_worker["headers"], sample_worker["id"])
        _create_interview(
            client,
            sample_worker["headers"],
            sample_worker["id"],
            interviewer="Second",
            status="completed",
        )
        _create_interview(
            client,
            sample_worker["headers"],
            sample_worker["id"],
            interviewer="Third",
            status="cancelled",
        )
        response = client.get("/api/interviews/stats", headers=sample_worker["headers"])
        assert response.status_code == 200
        assert response.json() == {
            "total": 3,
            "upcoming": 1,
            "completed": 1,
            "cancelled": 1,
        }

    def test_stats_empty(self, client, user):
        response = client.get("/api/interviews/stats", headers=user["headers"])
        assert response.json() == {"total": 0, "upcoming": 0, "completed": 0, "cancelled": 0}

    def test_stats_only_counts_own_interviews(self, client, sample_worker, other_user):
        _create_interview(client, sample_worker["headers"], sample_worker["id"])
        response = client.get("/api/interviews/stats", headers=other_user["headers"])
        assert response.json()["total"] == 0

    def test_stats_requires_auth(self, client):
        assert client.get("/api/interviews/stats").status_code == 401


# ---------------------------------------------------------------------------
# Interview CRUD functions
# ---------------------------------------------------------------------------


class TestInterviewCrud:
    def _create_owned_interview(self, db_session, owner, fields=None):
        job = _create_job_with_owner(db_session, owner.id)
        worker = _create_worker(db_session, job.id)
        return interview_crud.create_interview(
            db_session,
            InterviewCreate(
                candidate_id=worker.id, **{**INTERVIEW_PAYLOAD, **(fields or {})}
            ),
            owner.id,
        )

    def test_create_interview_sets_hr_id(self, db_session):
        owner = _create_owner(db_session)
        interview = self._create_owned_interview(db_session, owner, {})
        assert interview.id is not None
        assert interview.hr_id == owner.id
        assert interview.status == InterviewStatus.UPCOMING

    def test_get_interview_by_id_is_scoped_to_hr(self, db_session):
        owner = _create_owner(db_session)
        other = _create_owner(db_session, email="other@example.com")
        interview = self._create_owned_interview(db_session, owner, {})
        assert interview_crud.get_interview_by_id(db_session, interview.id, owner.id) is interview
        assert interview_crud.get_interview_by_id(db_session, interview.id, other.id) is None

    def test_list_interviews_supports_status_and_search(self, db_session):
        owner = _create_owner(db_session)
        self._create_owned_interview(db_session, owner, {})
        self._create_owned_interview(
            db_session,
            owner,
            {"interviewer": "Peter Frontend", "status": "completed"},
        )
        assert len(interview_crud.get_interviews(db_session, owner.id)) == 2
        by_status = interview_crud.get_interviews(
            db_session, owner.id, status=InterviewStatus.COMPLETED
        )
        assert [row.interviewer for row in by_status] == ["Peter Frontend"]
        by_search = interview_crud.get_interviews(db_session, owner.id, search="anna")
        assert [row.interviewer for row in by_search] == ["Anna HR"]
        # Candidate/job are eager-loaded so response building has no lazy loads.
        assert by_status[0].candidate.job.company_name == "Acme Corp"

    def test_get_interview_stats(self, db_session):
        owner = _create_owner(db_session)
        self._create_owned_interview(db_session, owner, {})
        self._create_owned_interview(db_session, owner, {"status": "cancelled"})
        assert interview_crud.get_interview_stats(db_session, owner.id) == {
            "total": 2,
            "upcoming": 1,
            "completed": 0,
            "cancelled": 1,
        }

    def test_update_interview_applies_only_submitted_fields(self, db_session):
        owner = _create_owner(db_session)
        interview = self._create_owned_interview(db_session, owner, {})
        updated = interview_crud.update_interview(
            db_session, interview, InterviewUpdate(status=InterviewStatus.COMPLETED)
        )
        assert updated.status == InterviewStatus.COMPLETED
        assert updated.interviewer == "Anna HR"  # untouched

    def test_delete_interview(self, db_session):
        owner = _create_owner(db_session)
        interview = self._create_owned_interview(db_session, owner, {})
        interview_crud.delete_interview(db_session, interview)
        assert interview_crud.get_interview_by_id(db_session, interview.id, owner.id) is None