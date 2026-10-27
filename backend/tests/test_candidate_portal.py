"""Candidate Portal: accounts, isolation, application tracking, safe AI feedback.

Scenario: an HR user publishes a job with an application form; candidates A
and B each apply while signed in. The tests check that each candidate sees
only their own data, that the HR <-> candidate token boundary holds in both
directions, and that HR-only information never reaches a candidate.
"""

import json

import pytest

from app.core.security import (
    TOKEN_PURPOSE_CANDIDATE_RESET,
    create_access_token,
    create_candidate_email_verification_token,
    create_candidate_token,
)
from app.crud import candidate_account as candidate_crud
from tests.payloads import INTERVIEW_PAYLOAD, JOB_PAYLOAD

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"
FIELDS = [
    {"label": "Full name", "type": "text", "required": True},
    {"label": "Email", "type": "email", "required": True},
    {"label": "Resume", "type": "file", "required": True},
]
ANALYSIS = {
    "match_percentage": 78.4,
    "summary": "INTERNAL SUMMARY for recruiters",
    "matched_requirements": ["Backend APIs"],
    "missing_requirements": ["Cloud deployment"],
    "matched_skills": ["Python", "FastAPI"],
    "missing_skills": ["Docker"],
    "strengths": ["INTERNAL strength"],
    "weaknesses": ["INTERNAL weakness"],
    "risks": ["INTERNAL risk"],
    "experience_analysis": "INTERNAL experience note",
    "education_analysis": "INTERNAL education note",
    "relevant_experience": [],
    "relevant_projects": [],
    "ai_recommendation": "do_not_hire",
    "analyzed_at": "2026-09-28T10:00:00Z",
}


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def _register_raw(client, email, name="Jane Candidate", password="CandidatePass1"):
    """Create a candidate account without confirming its email."""
    return client.post(
        "/api/candidate/auth/register",
        json={"email": email, "full_name": name, "password": password},
    )


def _verify_candidate(client, response):
    """Confirm a just-registered candidate's email (test helper on the real endpoint)."""
    if response.status_code != 201:
        return response
    candidate_id = response.json()["candidate"]["id"]
    token = create_candidate_email_verification_token(candidate_id)
    client.post("/api/candidate/auth/verify-email", json={"token": token})
    return response


def _register(client, email, name="Jane Candidate", password="CandidatePass1"):
    """Register a candidate and confirm the email so the portal is usable."""
    return _verify_candidate(client, _register_raw(client, email, name=name, password=password))


@pytest.fixture
def job(client, user):
    response = client.post(
        "/api/jobs", json={**JOB_PAYLOAD, "application_form": {"fields": FIELDS}}, headers=user["headers"]
    )
    assert response.status_code == 201, response.text
    return response.json()


def _apply(client, job, email, headers=None):
    token = job["application_form"]["public_token"]
    ids = {f["label"]: f["id"] for f in job["application_form"]["fields"]}
    values = {ids["Full name"]: "Applicant", ids["Email"]: email}
    return client.post(
        f"/api/public/applications/{token}/submit",
        files={
            "values": (None, json.dumps(values)),
            ids["Resume"]: ("cv.pdf", PDF, "application/pdf"),
        },
        headers=headers,
    )


def _candidate(client, email):
    response = _register(client, email)
    assert response.status_code == 201, response.text
    body = response.json()
    return {"headers": _bearer(body["access_token"]), "body": body, "email": email}


def _only_application(client, candidate):
    apps = client.get("/api/candidate/applications", headers=candidate["headers"]).json()
    assert len(apps) == 1, apps
    return apps[0]


@pytest.fixture
def world(client, user, job):
    a = _candidate(client, "a@example.com")
    b = _candidate(client, "b@example.com")
    assert _apply(client, job, a["email"], a["headers"]).status_code == 201
    assert _apply(client, job, b["email"], b["headers"]).status_code == 201
    a["application_id"] = _only_application(client, a)["id"]
    b["application_id"] = _only_application(client, b)["id"]
    return {"hr": user, "a": a, "b": b, "job": job}


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------


class TestCandidateAccounts:
    def test_register_returns_tokens_and_profile(self, client):
        response = _register(client, "New@Example.com")
        assert response.status_code == 201
        body = response.json()
        assert body["candidate"]["email"] == "new@example.com"
        assert body["access_token"] and body["refresh_token"]
        assert "hashed_password" not in json.dumps(body)

    def test_duplicate_email_is_rejected(self, client):
        assert _register(client, "dup@example.com").status_code == 201
        assert _register(client, "DUP@example.com").status_code == 409

    @pytest.mark.parametrize(
        "payload",
        [
            {"email": "not-an-email", "full_name": "X", "password": "LongEnough1"},
            {"email": "x@example.com", "full_name": "   ", "password": "LongEnough1"},
            {"email": "x@example.com", "full_name": "X", "password": "short"},
            {"email": "x@example.com", "full_name": "X", "password": "x" * 73},
        ],
    )
    def test_invalid_registration(self, client, payload):
        assert client.post("/api/candidate/auth/register", json=payload).status_code == 422

    def test_login(self, client):
        _register(client, "login@example.com", password="CandidatePass1")
        ok = client.post(
            "/api/candidate/auth/login", json={"email": "login@example.com", "password": "CandidatePass1"}
        )
        assert ok.status_code == 200 and ok.json()["candidate"]["email"] == "login@example.com"
        wrong = client.post(
            "/api/candidate/auth/login", json={"email": "login@example.com", "password": "nope-nope"}
        )
        assert wrong.status_code == 401
        unknown = client.post(
            "/api/candidate/auth/login", json={"email": "ghost@example.com", "password": "nope-nope"}
        )
        assert unknown.status_code == 401 and unknown.json()["detail"] == wrong.json()["detail"]

    def test_inactive_account_cannot_sign_in_or_use_tokens(self, client, db_session):
        candidate = _candidate(client, "inactive@example.com")
        account = candidate_crud.get_by_email(db_session, "inactive@example.com")
        candidate_crud.update(db_session, account, {"is_active": False})
        login = client.post(
            "/api/candidate/auth/login", json={"email": "inactive@example.com", "password": "CandidatePass1"}
        )
        assert login.status_code == 401
        assert client.get("/api/candidate/profile", headers=candidate["headers"]).status_code == 401

    def test_candidate_random_credentials_fails(self, client):
        """Random credentials must be rejected by candidate login."""
        res = client.post(
            "/api/candidate/auth/login", json={"email": "random123@example.com", "password": "randomPassword123"}
        )
        assert res.status_code == 401
        assert res.json()["detail"] == "Incorrect email or password."

    def test_candidate_google_login_flow(self, client, monkeypatch):
        """Candidate can register and login via Google OAuth."""
        from app.services.google_auth import GoogleUserProfile
        from app.services import candidate_auth

        async def fake_authenticate(code, redirect_uri=None):  # noqa: ARG001
            return GoogleUserProfile(
                google_id="cand-google-12345",
                email="candidate.google@example.com",
                full_name="Google Candidate",
                picture="https://example.com/cand.jpg",
            )

        monkeypatch.setattr(candidate_auth, "authenticate_with_google", fake_authenticate)
        res = client.post("/api/candidate/auth/google", json={"code": "cand-auth-code-123"})
        assert res.status_code == 200
        data = res.json()
        assert data["candidate"]["email"] == "candidate.google@example.com"
        assert data["candidate"]["full_name"] == "Google Candidate"
        assert "access_token" in data and "refresh_token" in data

    def test_candidate_google_login_links_existing_candidate(self, client, monkeypatch):
        """Candidate Google login links an existing password account by email."""
        from app.services.google_auth import GoogleUserProfile
        from app.services import candidate_auth

        _register(client, "existing.cand@example.com", name="Original Name")

        async def fake_authenticate(code, redirect_uri=None):  # noqa: ARG001
            return GoogleUserProfile(
                google_id="cand-google-linked-123",
                email="existing.cand@example.com",
                full_name="Original Name",
                picture="https://example.com/avatar.jpg",
            )

        monkeypatch.setattr(candidate_auth, "authenticate_with_google", fake_authenticate)
        res = client.post("/api/candidate/auth/google", json={"code": "cand-auth-code-456"})
        assert res.status_code == 200

    def test_candidate_google_only_account_rejects_password_login(self, client, db_session):
        """A candidate who signed in via Google only (no password) cannot use password login."""
        candidate_crud.get_or_create_google_candidate(
            db_session,
            google_id="google-only-cand-id",
            email="google.candidate@example.com",
            full_name="Google Cand",
            picture=None,
        )
        res = client.post(
            "/api/candidate/auth/login",
            json={"email": "google.candidate@example.com", "password": "arbitraryPassword123"},
        )
        assert res.status_code == 401

    def test_password_account_profile_reports_has_password(self, client):
        body = _register(client, "haspass@example.com").json()
        assert body["candidate"]["has_password"] is True
        profile = client.get("/api/candidate/profile", headers=_bearer(body["access_token"]))
        assert profile.status_code == 200
        assert profile.json()["has_password"] is True

    def test_google_only_candidate_cannot_change_password(self, client, monkeypatch):
        """A Google-only candidate must get a clean 400 (never a bcrypt-on-NULL 500)."""
        from app.services.google_auth import GoogleUserProfile
        from app.services import candidate_auth

        async def fake_authenticate(code, redirect_uri=None):  # noqa: ARG001
            return GoogleUserProfile(
                google_id="cand-google-only-change",
                email="google.only.change@example.com",
                full_name="Google Only",
                picture=None,
            )

        monkeypatch.setattr(candidate_auth, "authenticate_with_google", fake_authenticate)
        login = client.post("/api/candidate/auth/google", json={"code": "cand-code"})
        assert login.status_code == 200
        token = login.json()["access_token"]
        assert login.json()["candidate"]["has_password"] is False

        res = client.patch(
            "/api/candidate/profile/password",
            json={"current_password": "whatever", "new_password": "BrandNewPass1"},
            headers=_bearer(token),
        )
        assert res.status_code == 400
        assert "does not have a password" in res.json()["detail"]

    def test_candidate_google_unverified_email_is_rejected(self, client, monkeypatch):
        """An unverified Google email must not be used to link/create an account."""
        from app.services.google_auth import GoogleUserProfile
        from app.services import candidate_auth

        async def fake_authenticate(code, redirect_uri=None):  # noqa: ARG001
            return GoogleUserProfile(
                google_id="cand-google-unverified",
                email="unverified.cand@example.com",
                full_name="Unverified",
                picture=None,
                email_verified=False,
            )

        monkeypatch.setattr(candidate_auth, "authenticate_with_google", fake_authenticate)
        res = client.post("/api/candidate/auth/google", json={"code": "cand-code"})
        assert res.status_code == 400
        assert "not verified" in res.json()["detail"]

    def test_cross_role_account_isolation_with_same_email(self, client, user_factory, monkeypatch):
        """HR User and Candidate with the same email retain strict separate role identities."""
        from app.services.google_auth import GoogleUserProfile
        from app.services import candidate_auth

        # Register HR user
        hr_res = user_factory(email="shared@example.com", password="StrongPassword123")
        assert hr_res.status_code == 201

        # Candidate Google OAuth with same email
        async def fake_authenticate(code, redirect_uri=None):  # noqa: ARG001
            return GoogleUserProfile(
                google_id="cand-google-shared",
                email="shared@example.com",
                full_name="Shared Candidate",
                picture=None,
            )

        monkeypatch.setattr(candidate_auth, "authenticate_with_google", fake_authenticate)
        cand_res = client.post("/api/candidate/auth/google", json={"code": "cand-code"})
        assert cand_res.status_code == 200
        cand_token = cand_res.json()["access_token"]

        # Candidate token is rejected on HR endpoints
        assert client.get("/api/jobs", headers=_bearer(cand_token)).status_code == 401
        # HR token is rejected on Candidate endpoints
        hr_token = hr_res.json()["access_token"]
        assert client.get("/api/candidate/profile", headers=_bearer(hr_token)).status_code == 401

    def test_invalid_and_missing_tokens(self, client):
        assert client.get("/api/candidate/dashboard").status_code == 401
        assert client.get("/api/candidate/dashboard", headers=_bearer("garbage")).status_code == 401

    def test_refresh_rotates_and_is_single_use(self, client):
        refresh_token = _register(client, "r@example.com").json()["refresh_token"]
        first = client.post("/api/candidate/auth/refresh", json={"refresh_token": refresh_token})
        assert first.status_code == 200
        replay = client.post("/api/candidate/auth/refresh", json={"refresh_token": refresh_token})
        assert replay.status_code == 401
        new_access = first.json()["access_token"]
        assert client.get("/api/candidate/profile", headers=_bearer(new_access)).status_code == 200

    def test_logout_revokes_tokens(self, client):
        body = _register(client, "out@example.com").json()
        headers = _bearer(body["access_token"])
        assert client.post(
            "/api/candidate/auth/logout", json={"refresh_token": body["refresh_token"]}, headers=headers
        ).status_code == 204
        assert client.get("/api/candidate/profile", headers=headers).status_code == 401
        assert client.post(
            "/api/candidate/auth/refresh", json={"refresh_token": body["refresh_token"]}
        ).status_code == 401

    def test_profile_update_and_password_change(self, client):
        candidate = _candidate(client, "p@example.com")
        _register(client, "taken@example.com")
        updated = client.patch(
            "/api/candidate/profile", json={"full_name": "Jane D.", "phone": "+998 90 000 00 00"},
            headers=candidate["headers"],
        )
        assert updated.status_code == 200 and updated.json()["phone"] == "+998 90 000 00 00"
        clash = client.patch("/api/candidate/profile", json={"email": "taken@example.com"}, headers=candidate["headers"])
        assert clash.status_code == 409

        wrong = client.patch(
            "/api/candidate/profile/password",
            json={"current_password": "wrong-one", "new_password": "BrandNewPass1"},
            headers=candidate["headers"],
        )
        assert wrong.status_code == 400
        changed = client.patch(
            "/api/candidate/profile/password",
            json={"current_password": "CandidatePass1", "new_password": "BrandNewPass1"},
            headers=candidate["headers"],
        )
        assert changed.status_code == 200
        # The old session is signed out; the returned one works.
        assert client.get("/api/candidate/profile", headers=candidate["headers"]).status_code == 401
        assert client.get("/api/candidate/profile", headers=_bearer(changed.json()["access_token"])).status_code == 200

    def test_password_reset(self, client, db_session):
        _register(client, "reset@example.com")
        assert client.post("/api/candidate/auth/forgot-password", json={"email": "reset@example.com"}).status_code == 200
        assert client.post("/api/candidate/auth/forgot-password", json={"email": "ghost@example.com"}).status_code == 200
        account = candidate_crud.get_by_email(db_session, "reset@example.com")
        token = create_candidate_token(account.id, TOKEN_PURPOSE_CANDIDATE_RESET)
        reset = client.post("/api/candidate/auth/reset-password", json={"token": token, "new_password": "ResetPass123"})
        assert reset.status_code == 200
        assert client.post("/api/candidate/auth/reset-password", json={"token": token, "new_password": "Again12345"}).status_code == 400
        login = client.post("/api/candidate/auth/login", json={"email": "reset@example.com", "password": "ResetPass123"})
        assert login.status_code == 200
        # A candidate access token is not a reset credential.
        access = login.json()["access_token"]
        assert client.post("/api/candidate/auth/reset-password", json={"token": access, "new_password": "Again12345"}).status_code == 400


# ---------------------------------------------------------------------------
# HR <-> candidate boundary
# ---------------------------------------------------------------------------


class TestTokenBoundary:
    HR_PATHS = ["/api/jobs", "/api/applications", "/api/interviews", "/api/dashboard/analytics", "/api/auth/me", "/api/users", "/api/admin/dashboard"]

    def test_candidate_token_cannot_reach_hr_endpoints(self, client, world):
        for path in self.HR_PATHS:
            assert client.get(path, headers=world["a"]["headers"]).status_code == 401, path
        app_id = world["a"]["application_id"]
        assert client.get(f"/api/applications/{app_id}", headers=world["a"]["headers"]).status_code == 401
        assert client.patch(
            f"/api/applications/{app_id}", json={"application_status": "hired"}, headers=world["a"]["headers"]
        ).status_code == 401
        assert client.get(f"/api/applications/{app_id}/resume", headers=world["a"]["headers"]).status_code == 401

    def test_hr_token_cannot_reach_candidate_endpoints(self, client, world):
        for path in ("/api/candidate/profile", "/api/candidate/dashboard", "/api/candidate/applications"):
            assert client.get(path, headers=world["hr"]["headers"]).status_code == 401, path

    def test_hr_token_with_same_numeric_id_is_rejected(self, client, world, db_session):
        account = candidate_crud.get_by_email(db_session, "a@example.com")
        forged = _bearer(create_access_token(account.id))
        assert client.get("/api/candidate/profile", headers=forged).status_code == 401

    def test_refresh_tokens_do_not_cross(self, client, world):
        candidate_refresh = world["a"]["body"]["refresh_token"]
        assert client.post("/api/auth/refresh", json={"refresh_token": candidate_refresh}).status_code == 401


# ---------------------------------------------------------------------------
# Applications, timeline, interviews, dashboard
# ---------------------------------------------------------------------------


class TestCandidateIsolation:
    def test_each_candidate_sees_only_own_applications(self, client, world):
        a_app, b_app = world["a"]["application_id"], world["b"]["application_id"]
        assert a_app != b_app
        assert client.get(f"/api/candidate/applications/{a_app}", headers=world["a"]["headers"]).status_code == 200
        for path in (f"/api/candidate/applications/{b_app}", f"/api/candidate/applications/{b_app}/resume"):
            assert client.get(path, headers=world["a"]["headers"]).status_code == 404, path

    def test_guest_submission_is_not_linked_to_any_account(self, client, world):
        # A guest applying with A's email never appears in A's portal
        # (emails are unverified, so linking by email would leak data).
        assert _apply(client, world["job"], world["a"]["email"] + ".other").status_code == 201
        assert len(client.get("/api/candidate/applications", headers=world["a"]["headers"]).json()) == 1

    def test_invalid_candidate_token_on_submit_is_rejected(self, client, world):
        response = _apply(client, world["job"], "x@example.com", headers=_bearer("garbage"))
        assert response.status_code == 401

    def test_own_resume_download(self, client, world):
        app_id = world["a"]["application_id"]
        response = client.get(f"/api/candidate/applications/{app_id}/resume", headers=world["a"]["headers"])
        assert response.status_code == 200 and response.content == PDF

    def test_interviews_are_scoped(self, client, world):
        hr = world["hr"]["headers"]
        created = client.post(
            "/api/interviews", json={**INTERVIEW_PAYLOAD, "candidate_id": world["a"]["application_id"]}, headers=hr
        )
        assert created.status_code == 201
        interview_id = created.json()["id"]

        mine = client.get("/api/candidate/interviews", headers=world["a"]["headers"]).json()
        assert [i["id"] for i in mine] == [interview_id]
        assert mine[0]["meeting_link"] == INTERVIEW_PAYLOAD["meeting_link"]
        assert "notes" not in mine[0] and "interviewer" not in mine[0]
        assert client.get("/api/candidate/interviews", headers=world["b"]["headers"]).json() == []
        assert client.get(f"/api/candidate/interviews/{interview_id}", headers=world["b"]["headers"]).status_code == 404
        assert client.get(f"/api/candidate/interviews/{interview_id}", headers=world["a"]["headers"]).status_code == 200

    def test_unsafe_meeting_links_are_not_exposed(self, client, world):
        client.post(
            "/api/interviews",
            json={**INTERVIEW_PAYLOAD, "meeting_link": "javascript:alert(1)", "candidate_id": world["a"]["application_id"]},
            headers=world["hr"]["headers"],
        )
        (interview,) = client.get("/api/candidate/interviews", headers=world["a"]["headers"]).json()
        assert interview["meeting_link"] is None and interview["is_online"] is False

    def test_dashboard_counts_only_own_data(self, client, world):
        hr = world["hr"]["headers"]
        client.post("/api/interviews", json={**INTERVIEW_PAYLOAD, "candidate_id": world["a"]["application_id"]}, headers=hr)
        client.patch(f"/api/applications/{world['b']['application_id']}", json={"application_status": "rejected"}, headers=hr)

        a = client.get("/api/candidate/dashboard", headers=world["a"]["headers"]).json()
        assert (a["total_applications"], a["active_applications"], a["upcoming_interviews"], a["completed_applications"]) == (1, 1, 1, 0)
        assert a["next_interview"]["application_id"] == world["a"]["application_id"]
        b = client.get("/api/candidate/dashboard", headers=world["b"]["headers"]).json()
        assert (b["total_applications"], b["active_applications"], b["upcoming_interviews"], b["completed_applications"]) == (1, 0, 0, 1)


class TestStatusAndTimeline:
    def _detail(self, client, candidate):
        return client.get(f"/api/candidate/applications/{candidate['application_id']}", headers=candidate["headers"]).json()

    def test_new_application(self, client, world):
        detail = self._detail(client, world["a"])
        assert detail["status"] == "submitted"
        assert detail["analysis"] == {
            "state": "not_analyzed", "match_percentage": None, "matched_skills": [], "skills_to_improve": [],
            "requirements_met": [], "requirements_to_strengthen": [], "analyzed_at": None,
        }
        steps = {s["key"]: s for s in detail["timeline"]}
        assert [s["key"] for s in detail["timeline"]] == ["submitted", "resume_review", "hr_review", "interview", "decision"]
        assert steps["submitted"]["state"] == "done" and steps["submitted"]["date"]
        assert steps["resume_review"]["state"] == "current"
        assert steps["hr_review"]["state"] == "upcoming" and steps["hr_review"]["date"] is None
        assert detail["job"]["position"] == JOB_PAYLOAD["position"]
        assert detail["has_resume"] is True
        resume_answer = next(a for a in detail["answers"] if a["type"] == "file")
        assert resume_answer == {"label": "Resume", "type": "file", "value": None, "file_attached": True}

    def test_status_progression_uses_friendly_states_and_real_dates(self, client, world):
        hr = world["hr"]["headers"]
        app_id = world["a"]["application_id"]
        client.patch(f"/api/applications/{app_id}", json={"application_status": "shortlisted"}, headers=hr)
        detail = self._detail(client, world["a"])
        assert detail["status"] == "hr_review"  # "shortlisted" is an HR term
        steps = {s["key"]: s for s in detail["timeline"]}
        assert steps["hr_review"]["state"] == "done" and steps["hr_review"]["date"]
        assert steps["resume_review"]["state"] == "skipped"
        assert steps["interview"]["state"] == "current"

        client.patch(f"/api/applications/{app_id}", json={"application_status": "interview"}, headers=hr)
        assert self._detail(client, world["a"])["status"] == "interview_invited"
        interview = client.post("/api/interviews", json={**INTERVIEW_PAYLOAD, "candidate_id": app_id}, headers=hr).json()
        detail = self._detail(client, world["a"])
        assert detail["status"] == "interview_scheduled" and detail["interview_state"] == "scheduled"
        client.patch(f"/api/interviews/{interview['id']}", json={"status": "completed"}, headers=hr)
        assert self._detail(client, world["a"])["status"] == "decision_pending"

        client.patch(f"/api/applications/{app_id}", json={"application_status": "hired"}, headers=hr)
        detail = self._detail(client, world["a"])
        assert detail["status"] == "accepted"
        decision = detail["timeline"][-1]
        assert decision == {**decision, "key": "decision", "state": "done", "outcome": "accepted"} and decision["date"]
        # Completed applications no longer expose a meeting link.
        assert detail["interviews"][0]["meeting_link"] is None

    def test_rejection_is_closed_not_scored(self, client, world):
        client.patch(
            f"/api/applications/{world['a']['application_id']}", json={"application_status": "rejected"},
            headers=world["hr"]["headers"],
        )
        detail = self._detail(client, world["a"])
        assert detail["status"] == "rejected"
        assert detail["timeline"][-1]["outcome"] == "rejected"


class TestSafeAIFeedback:
    def _set_analysis(self, db_session, application_id, status, details=None):
        from app.models.application import AnalysisStatus, Application

        application = db_session.get(Application, application_id)
        application.analysis_status = AnalysisStatus(status)
        application.ai_analysis_details = details
        application.ai_score = 91
        application.analysis_error = "provider said: INTERNAL error 500 key=sk-xyz"
        db_session.commit()

    def test_analyzed_feedback_excludes_internal_fields(self, client, world, db_session):
        self._set_analysis(db_session, world["a"]["application_id"], "completed", ANALYSIS)
        response = client.get(f"/api/candidate/applications/{world['a']['application_id']}", headers=world["a"]["headers"])
        body = response.json()
        assert body["analysis"] == {
            "state": "analyzed",
            "match_percentage": 78,
            "matched_skills": ["Python", "FastAPI"],
            "skills_to_improve": ["Docker"],
            "requirements_met": ["Backend APIs"],
            "requirements_to_strengthen": ["Cloud deployment"],
            "analyzed_at": "2026-09-28T10:00:00Z",
        }
        raw = response.text
        for secret in ("INTERNAL", "do_not_hire", "ai_recommendation", "ai_score", "sk-xyz", "hiring_status", "owner"):
            assert secret not in raw, secret
        resume_step = next(s for s in body["timeline"] if s["key"] == "resume_review")
        assert resume_step["state"] == "done" and resume_step["date"] == "2026-09-28T10:00:00Z"

    def test_failed_analysis_is_not_an_application_failure(self, client, world, db_session):
        self._set_analysis(db_session, world["a"]["application_id"], "failed")
        response = client.get(f"/api/candidate/applications/{world['a']['application_id']}", headers=world["a"]["headers"])
        body = response.json()
        assert body["status"] == "submitted"
        assert body["analysis"]["state"] == "failed"
        assert next(s for s in body["timeline"] if s["key"] == "resume_review")["state"] == "unavailable"
        assert "sk-xyz" not in response.text and "provider" not in response.text

    def test_analyzing_state(self, client, world, db_session):
        self._set_analysis(db_session, world["a"]["application_id"], "analyzing")
        body = client.get(f"/api/candidate/applications/{world['a']['application_id']}", headers=world["a"]["headers"]).json()
        assert body["status"] == "ai_review" and body["analysis"]["state"] == "analyzing"


class TestHRSideUnchanged:
    def test_hr_sees_linked_application_and_can_set_hired(self, client, world):
        hr = world["hr"]["headers"]
        apps = client.get("/api/applications", headers=hr).json()
        assert {a["id"] for a in apps} == {world["a"]["application_id"], world["b"]["application_id"]}
        response = client.patch(f"/api/applications/{world['a']['application_id']}", json={"application_status": "hired"}, headers=hr)
        assert response.status_code == 200 and response.json()["application_status"] == "hired"
        assert client.get("/api/dashboard/analytics", headers=hr).status_code == 200
