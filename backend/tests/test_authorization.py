"""Authorization model: admin = every HR permission + admin-only permissions.

Scenario used throughout: HR-A (``user``) and HR-B (``other_user``) each own a
job with one application; the admin (``admin``, signed in to the admin
workspace) owns nothing. The tests check that

* each HR user has full access to their own resources and none to the other's,
* an admin session runs the *same* HR actions (not just reads) on any HR
  user's resources, and sees organisation-wide lists and dashboards,
* a superuser who chose the HR workspace is scoped like a regular HR user,
* user management stays admin-only.
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.core.security import create_access_token
from app.schemas.application_analysis import ApplicationAnalysis
from tests.payloads import APPLICATION_PAYLOAD, INTERVIEW_PAYLOAD, JOB_PAYLOAD

ANALYSIS = ApplicationAnalysis(
    match_percentage=81,
    summary="Good fit.",
    matched_requirements=["Python"],
    missing_requirements=[],
    matched_skills=["Python"],
    missing_skills=[],
    strengths=["APIs"],
    weaknesses=[],
    risks=[],
    experience_analysis="3 years.",
    education_analysis="BSc.",
    relevant_experience=[],
    relevant_projects=[],
    ai_recommendation="hire",
)


def _create_job(client, headers, **overrides):
    response = client.post("/api/jobs", json={**JOB_PAYLOAD, **overrides}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def _create_application(client, headers, job_id, email="jane@example.com"):
    response = client.post(
        f"/api/applications?job_id={job_id}",
        json={**APPLICATION_PAYLOAD, "email": email},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _schedule(client, headers, candidate_id):
    return client.post(
        "/api/interviews", json={**INTERVIEW_PAYLOAD, "candidate_id": candidate_id}, headers=headers
    )


@pytest.fixture
def world(client, user, other_user, admin):
    """HR-A and HR-B each own a job + application (+ interview)."""
    data = {"a": user, "b": other_user, "admin": admin}
    for key, hr in (("a", user), ("b", other_user)):
        job = _create_job(client, hr["headers"], company_name=f"Company {key.upper()}")
        application = _create_application(client, hr["headers"], job["id"], email=f"{key}@example.com")
        interview = _schedule(client, hr["headers"], application["id"])
        assert interview.status_code == 201, interview.text
        hr.update(job=job, application=application, interview=interview.json())
    return data


def _full_hr_actions(client, headers, owner):
    """Run every HR mutation on ``owner``'s resources and assert success."""
    job_id = owner["job"]["id"]
    app_id = owner["application"]["id"]
    interview_id = owner["interview"]["id"]

    assert client.get(f"/api/jobs/{job_id}", headers=headers).status_code == 200
    updated = client.put(f"/api/jobs/{job_id}", json={"position": "Renamed"}, headers=headers)
    assert updated.status_code == 200 and updated.json()["position"] == "Renamed"

    assert client.get(f"/api/applications/{app_id}", headers=headers).status_code == 200
    status_update = client.patch(
        f"/api/applications/{app_id}",
        json={"application_status": "shortlisted", "hiring_status": "hire"},
        headers=headers,
    )
    assert status_update.status_code == 200, status_update.text
    assert status_update.json()["application_status"] == "shortlisted"
    converted = client.post(f"/api/applications/{app_id}/convert-to-candidate", headers=headers)
    assert converted.status_code == 200 and converted.json()["is_candidate"] is True
    with patch(
        "app.services.application_analysis.analyze_application", new_callable=AsyncMock
    ) as mock_analyze:
        mock_analyze.return_value = ANALYSIS
        analyzed = client.post(f"/api/applications/{app_id}/analyze", headers=headers)
    assert analyzed.status_code == 200, analyzed.text
    assert analyzed.json()["analysis_status"] == "completed"
    assert client.get(f"/api/applications/{app_id}/analysis", headers=headers).status_code == 200

    scheduled = _schedule(client, headers, app_id)
    assert scheduled.status_code == 201, scheduled.text
    changed = client.patch(
        f"/api/interviews/{interview_id}",
        json={"status": "completed", "interviewer": "Bob", "notes": "Went well"},
        headers=headers,
    )
    assert changed.status_code == 200 and changed.json()["status"] == "completed"
    assert client.delete(f"/api/interviews/{scheduled.json()['id']}", headers=headers).status_code == 204

    assert client.delete(f"/api/applications/{app_id}", headers=headers).status_code == 204
    assert client.delete(f"/api/jobs/{job_id}", headers=headers).status_code == 204
    assert client.get(f"/api/jobs/{job_id}", headers=headers).status_code == 404


def _assert_no_access(client, headers, owner):
    """Every read and write on ``owner``'s resources looks like "not found"."""
    job_id = owner["job"]["id"]
    app_id = owner["application"]["id"]
    interview_id = owner["interview"]["id"]
    responses = [
        client.get(f"/api/jobs/{job_id}", headers=headers),
        client.put(f"/api/jobs/{job_id}", json={"position": "x"}, headers=headers),
        client.delete(f"/api/jobs/{job_id}", headers=headers),
        client.get(f"/api/jobs/{job_id}/application-form", headers=headers),
        client.get(f"/api/applications/{app_id}", headers=headers),
        client.patch(f"/api/applications/{app_id}", json={"application_status": "rejected"}, headers=headers),
        client.delete(f"/api/applications/{app_id}", headers=headers),
        client.post(f"/api/applications/{app_id}/analyze", headers=headers),
        client.post(f"/api/applications/{app_id}/convert-to-candidate", headers=headers),
        client.get(f"/api/applications/{app_id}/resume", headers=headers),
        client.post(f"/api/applications?job_id={job_id}", json=APPLICATION_PAYLOAD, headers=headers),
        _schedule(client, headers, app_id),
        client.get(f"/api/interviews/{interview_id}", headers=headers),
        client.patch(f"/api/interviews/{interview_id}", json={"status": "cancelled"}, headers=headers),
        client.delete(f"/api/interviews/{interview_id}", headers=headers),
    ]
    assert [r.status_code for r in responses] == [404] * len(responses)


class TestHRIsolation:
    def test_hr_has_full_access_to_own_resources(self, client, world):
        _full_hr_actions(client, world["a"]["headers"], world["a"])

    def test_hr_cannot_touch_another_hrs_resources(self, client, world):
        _assert_no_access(client, world["a"]["headers"], world["b"])
        _assert_no_access(client, world["b"]["headers"], world["a"])
        # Nothing was changed by the denied attempts.
        b = world["b"]
        assert client.get(f"/api/jobs/{b['job']['id']}", headers=b["headers"]).json()["position"] == JOB_PAYLOAD["position"]
        detail = client.get(f"/api/applications/{b['application']['id']}", headers=b["headers"]).json()
        assert detail["application_status"] == "new"

    def test_hr_lists_and_dashboard_only_show_own_data(self, client, world):
        headers = world["a"]["headers"]
        assert [j["id"] for j in client.get("/api/jobs", headers=headers).json()] == [world["a"]["job"]["id"]]
        assert [a["id"] for a in client.get("/api/applications", headers=headers).json()] == [
            world["a"]["application"]["id"]
        ]
        assert [i["id"] for i in client.get("/api/interviews", headers=headers).json()] == [
            world["a"]["interview"]["id"]
        ]
        assert client.get("/api/interviews/stats", headers=headers).json()["total"] == 1
        assert len(client.get("/api/dashboard/recent-jobs", headers=headers).json()) == 1
        assert len(client.get("/api/dashboard/recent-leads", headers=headers).json()) == 1
        overview = client.get("/api/dashboard/overview", headers=headers).json()
        assert overview["total_jobs"] == 1
        analytics = client.get("/api/dashboard/analytics", headers=headers)
        assert analytics.status_code == 200

    def test_hr_cannot_filter_by_another_hrs_job(self, client, world):
        response = client.get(
            f"/api/applications?job_id={world['b']['job']['id']}", headers=world["a"]["headers"]
        )
        assert response.status_code == 404

    def test_hr_cannot_use_user_management(self, client, world):
        headers = world["a"]["headers"]
        b_id = world["b"]["id"]
        assert client.get("/api/users", headers=headers).status_code == 403
        assert client.get(f"/api/users/{b_id}", headers=headers).status_code == 403
        assert client.put(f"/api/users/{b_id}", json={"is_active": False}, headers=headers).status_code == 403
        assert client.put(f"/api/users/{b_id}", json={"is_superuser": True}, headers=headers).status_code == 403
        assert client.delete(f"/api/users/{b_id}", headers=headers).status_code == 403
        assert client.get("/api/admin/dashboard", headers=headers).status_code == 403


class TestAdminHasEveryHRPermission:
    def test_admin_can_create_and_manage_own_job(self, client, world):
        headers = world["admin"]["headers"]
        job = _create_job(client, headers)
        application = _create_application(client, headers, job["id"])
        interview = _schedule(client, headers, application["id"])
        assert interview.status_code == 201
        own = {"job": job, "application": application, "interview": interview.json()}
        _full_hr_actions(client, headers, own)

    def test_admin_has_full_access_to_each_hrs_resources(self, client, world):
        _full_hr_actions(client, world["admin"]["headers"], world["a"])
        _full_hr_actions(client, world["admin"]["headers"], world["b"])

    def test_admin_can_update_application_status(self, client, world):
        """The reported bug: admin could read the status but not change it."""
        app_id = world["b"]["application"]["id"]
        for status_value in ("reviewing", "interview", "rejected"):
            response = client.patch(
                f"/api/applications/{app_id}",
                json={"application_status": status_value},
                headers=world["admin"]["headers"],
            )
            assert response.status_code == 200, response.text
            assert response.json()["application_status"] == status_value
        # The owning HR sees the admin's change.
        owner_view = client.get(f"/api/applications/{app_id}", headers=world["b"]["headers"]).json()
        assert owner_view["application_status"] == "rejected"

    def test_admin_scheduled_interview_stays_with_candidate_owner(self, client, world):
        b = world["b"]
        created = _schedule(client, world["admin"]["headers"], b["application"]["id"])
        assert created.status_code == 201
        assert created.json()["hr_id"] == b["id"]
        # HR-B sees it and can manage it; HR-A cannot.
        ids = [i["id"] for i in client.get("/api/interviews", headers=b["headers"]).json()]
        assert created.json()["id"] in ids
        assert client.patch(
            f"/api/interviews/{created.json()['id']}", json={"status": "cancelled"}, headers=b["headers"]
        ).status_code == 200
        assert client.get(f"/api/interviews/{created.json()['id']}", headers=world["a"]["headers"]).status_code == 404

    def test_admin_moving_interview_reassigns_owner(self, client, world):
        interview_id = world["a"]["interview"]["id"]
        moved = client.patch(
            f"/api/interviews/{interview_id}",
            json={"candidate_id": world["b"]["application"]["id"]},
            headers=world["admin"]["headers"],
        )
        assert moved.status_code == 200
        assert moved.json()["hr_id"] == world["b"]["id"]
        assert client.get(f"/api/interviews/{interview_id}", headers=world["b"]["headers"]).status_code == 200
        assert client.get(f"/api/interviews/{interview_id}", headers=world["a"]["headers"]).status_code == 404

    def test_hr_cannot_move_interview_to_another_hrs_candidate(self, client, world):
        response = client.patch(
            f"/api/interviews/{world['a']['interview']['id']}",
            json={"candidate_id": world["b"]["application"]["id"]},
            headers=world["a"]["headers"],
        )
        assert response.status_code == 404

    def test_admin_can_add_application_and_manage_form_on_hr_job(self, client, world):
        headers = world["admin"]["headers"]
        job_id = world["a"]["job"]["id"]
        _create_application(client, headers, job_id, email="manual@example.com")
        form = client.put(
            f"/api/jobs/{job_id}/application-form",
            json={"fields": []},
            headers=headers,
        )
        # Either saved or rejected by form validation, never hidden from the admin.
        assert form.status_code in (200, 422)

    def test_admin_lists_and_dashboard_are_organisation_wide(self, client, world):
        headers = world["admin"]["headers"]
        job_ids = {j["id"] for j in client.get("/api/jobs", headers=headers).json()}
        assert job_ids == {world["a"]["job"]["id"], world["b"]["job"]["id"]}
        app_ids = {a["id"] for a in client.get("/api/applications", headers=headers).json()}
        assert app_ids == {world["a"]["application"]["id"], world["b"]["application"]["id"]}
        filtered = client.get(f"/api/applications?job_id={world['b']['job']['id']}", headers=headers)
        assert [a["id"] for a in filtered.json()] == [world["b"]["application"]["id"]]
        assert len(client.get("/api/interviews", headers=headers).json()) == 2
        assert client.get("/api/interviews/stats", headers=headers).json()["total"] == 2
        assert len(client.get("/api/dashboard/recent-jobs", headers=headers).json()) == 2
        assert len(client.get("/api/dashboard/recent-leads", headers=headers).json()) == 2
        assert client.get("/api/dashboard/overview", headers=headers).json()["total_jobs"] == 2
        analytics = client.get("/api/dashboard/analytics", headers=headers)
        assert analytics.status_code == 200

    def test_admin_auto_analyze_covers_every_hr(self, client, world):
        headers = world["admin"]["headers"]
        available = client.get("/api/applications/auto-analyze/available", headers=headers).json()
        assert available["count"] == 2
        assert {o["company_name"] for o in available["options"]} == {"Company A", "Company B"}
        # HR-A still only sees their own.
        own = client.get("/api/applications/auto-analyze/available", headers=world["a"]["headers"]).json()
        assert own["count"] == 1

    def test_admin_batch_analyses_every_hrs_applications(self, client, world, db_session):
        from app.crud.user import get_user_by_id
        from app.services.ai import batch as batch_service

        admin_user = get_user_by_id(db_session, world["admin"]["id"])
        batch = batch_service.create_auto_analyze_batch(db_session, admin_user, count=10, all_owners=True)
        assert sorted(batch.application_ids) == sorted(
            [world["a"]["application"]["id"], world["b"]["application"]["id"]]
        )
        with patch(
            "app.services.application_analysis.analyze_application", new_callable=AsyncMock
        ) as mock_analyze:
            mock_analyze.return_value = ANALYSIS
            asyncio.run(batch_service.run_batch_analysis(batch.id))

        progress = client.get(f"/api/applications/auto-analyze/{batch.id}", headers=world["admin"]["headers"])
        assert progress.status_code == 200
        body = progress.json()
        assert body["status"] == "completed" and body["successful"] == 2 and body["skipped"] == 0
        # Another HR user cannot read the admin's batch.
        assert client.get(
            f"/api/applications/auto-analyze/{batch.id}", headers=world["a"]["headers"]
        ).status_code == 404

    def test_admin_can_still_manage_users(self, client, world):
        headers = world["admin"]["headers"]
        b_id = world["b"]["id"]
        assert client.get("/api/users", headers=headers).status_code == 200
        assert client.get(f"/api/users/{b_id}", headers=headers).status_code == 200
        assert client.put(f"/api/users/{b_id}", json={"is_active": False}, headers=headers).json()["is_active"] is False
        assert client.put(f"/api/users/{b_id}", json={"is_active": True}, headers=headers).json()["is_active"] is True
        assert client.put(f"/api/users/{b_id}", json={"is_superuser": True}, headers=headers).json()["is_superuser"] is True
        assert client.put(f"/api/users/{b_id}", json={"is_superuser": False}, headers=headers).json()["is_superuser"] is False
        assert client.get("/api/admin/dashboard", headers=headers).status_code == 200
        assert client.delete(f"/api/users/{b_id}", headers=headers).status_code == 204


class TestAdminWorkspaceScope:
    def test_superuser_in_hr_workspace_is_scoped_like_hr(self, client, world):
        """The org-wide scope needs an admin session, like every admin power."""
        hr_session = {"Authorization": f"Bearer {create_access_token(world['admin']['id'], role='user')}"}
        _assert_no_access(client, hr_session, world["a"])
        assert client.get("/api/jobs", headers=hr_session).json() == []
        # Their own HR work is unaffected.
        job = _create_job(client, hr_session)
        assert client.put(f"/api/jobs/{job['id']}", json={"position": "Mine"}, headers=hr_session).status_code == 200

    def test_admin_claim_without_superuser_grants_nothing(self, client, world):
        forged = {"Authorization": f"Bearer {create_access_token(world['a']['id'], role='admin')}"}
        _assert_no_access(client, forged, world["b"])
        assert [j["id"] for j in client.get("/api/jobs", headers=forged).json()] == [world["a"]["job"]["id"]]

    def test_demoted_admin_loses_org_wide_access_immediately(self, client, world, db_session):
        from app.crud.user import get_user_by_id

        headers = world["admin"]["headers"]
        assert client.get(f"/api/jobs/{world['a']['job']['id']}", headers=headers).status_code == 200
        admin_user = get_user_by_id(db_session, world["admin"]["id"])
        admin_user.is_superuser = False
        db_session.commit()
        assert client.get(f"/api/jobs/{world['a']['job']['id']}", headers=headers).status_code == 404
