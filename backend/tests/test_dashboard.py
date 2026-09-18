"""Tests for dashboard endpoints and analytics.

The dashboard is user-scoped: it only aggregates the *current* HR user's jobs
and candidates. Aggregation numbers are verified exactly.
"""

from tests.payloads import JOB_PAYLOAD, WORKER_PAYLOAD


def _create_job(client, headers, **overrides):
    payload = dict(JOB_PAYLOAD, **overrides)
    response = client.post("/api/jobs", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def _create_worker(client, headers, job_id, name):
    payload = dict(WORKER_PAYLOAD, name=name)
    response = client.post(f"/api/workers?job_id={job_id}", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


# ---------------------------------------------------------------------------
# /dashboard/overview
# ---------------------------------------------------------------------------


class TestOverview:
    def test_overview_empty_database(self, client, user):
        response = client.get("/api/dashboard/overview", headers=user["headers"])
        assert response.status_code == 200
        body = response.json()
        assert body == {
            "total_jobs": 0,
            "total_candidates": 0,
            "total_leads": 0,
            "group_by": "company",
            "breakdown": [],
        }

    def test_overview_aggregates_by_company(self, client, user):
        job1 = _create_job(client, user["headers"], company_name="Acme Corp", position="Backend Developer")
        job2 = _create_job(client, user["headers"], company_name="Acme Corp", position="Data Engineer")
        job3 = _create_job(client, user["headers"], company_name="Globex", position="QA Engineer")
        _create_worker(client, user["headers"], job1["id"], "Worker A")
        _create_worker(client, user["headers"], job1["id"], "Worker B")
        _create_worker(client, user["headers"], job3["id"], "Worker C")

        body = client.get("/api/dashboard/overview", headers=user["headers"]).json()

        assert body["total_jobs"] == 3
        assert body["total_candidates"] == 3
        assert body["total_leads"] == 3  # sum of per-job leads_count (2 + 0 + 1)
        assert body["group_by"] == "company"
        breakdown = {row["category"]: row for row in body["breakdown"]}
        assert breakdown["Acme Corp"]["jobs"] == 2
        assert breakdown["Acme Corp"]["candidates"] == 2
        assert breakdown["Globex"]["jobs"] == 1
        assert breakdown["Globex"]["candidates"] == 1

    def test_overview_group_by_position(self, client, user):
        job1 = _create_job(client, user["headers"], position="Backend Developer")
        job2 = _create_job(client, user["headers"], position="Data Engineer")
        _create_worker(client, user["headers"], job1["id"], "Worker A")
        _create_worker(client, user["headers"], job1["id"], "Worker B")
        _create_worker(client, user["headers"], job2["id"], "Worker C")

        body = client.get("/api/dashboard/overview?category=position", headers=user["headers"]).json()
        breakdown = {row["category"]: row for row in body["breakdown"]}
        assert body["total_jobs"] == 2
        assert body["total_candidates"] == 3
        assert breakdown["Backend Developer"] == {"category": "Backend Developer", "jobs": 1, "candidates": 2}
        assert breakdown["Data Engineer"] == {"category": "Data Engineer", "jobs": 1, "candidates": 1}

# ---------------------------------------------------------------------------
# /dashboard/recent-leads
# ---------------------------------------------------------------------------


class TestRecentLeads:
    def test_recent_leads_returns_newest_first(self, client, user):
        job = _create_job(client, user["headers"])
        _create_worker(client, user["headers"], job["id"], "Oldest")
        _create_worker(client, user["headers"], job["id"], "Middle")
        _create_worker(client, user["headers"], job["id"], "Newest")

        response = client.get("/api/dashboard/recent-leads", headers=user["headers"])
        assert response.status_code == 200
        leads = response.json()
        assert [lead["name"] for lead in leads] == ["Newest", "Middle", "Oldest"]
        # Each lead includes its job context, not just the worker fields.
        assert leads[0]["company_name"] == "Acme Corp"
        assert leads[0]["position"] == "Backend Developer"
        assert leads[0]["hiring_status"] == "hire"

    def test_recent_leads_respects_limit(self, client, user):
        job = _create_job(client, user["headers"])
        _create_worker(client, user["headers"], job["id"], "A")
        _create_worker(client, user["headers"], job["id"], "B")
        leads = client.get("/api/dashboard/recent-leads?limit=1", headers=user["headers"]).json()
        assert len(leads) == 1

    def test_recent_leads_requires_auth(self, client):
        assert client.get("/api/dashboard/recent-leads").status_code == 401


# ---------------------------------------------------------------------------
# /dashboard/recent-jobs
# ---------------------------------------------------------------------------


class TestRecentJobs:
    def test_recent_jobs_returns_newest_first(self, client, user):
        _create_job(client, user["headers"], position="First")
        job2 = _create_job(client, user["headers"], position="Second")
        _create_worker(client, user["headers"], job2["id"], "Worker A")

        response = client.get("/api/dashboard/recent-jobs", headers=user["headers"])
        assert response.status_code == 200
        jobs = response.json()
        assert [job["position"] for job in jobs] == ["Second", "First"]
        assert jobs[0]["leads_count"] == 1

    def test_recent_jobs_respects_limit(self, client, user):
        _create_job(client, user["headers"], position="First")
        _create_job(client, user["headers"], position="Second")
        jobs = client.get("/api/dashboard/recent-jobs?limit=1", headers=user["headers"]).json()
        assert len(jobs) == 1

    def test_recent_jobs_requires_auth(self, client):
        assert client.get("/api/dashboard/recent-jobs").status_code == 401


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class TestHealth:
    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
    def test_overview_only_counts_own_data(self, client, user, other_user):
        _create_worker(client, user["headers"], _create_job(client, user["headers"])["id"], "Mine")

        body = client.get("/api/dashboard/overview", headers=other_user["headers"]).json()
        assert body["total_jobs"] == 0
        assert body["total_candidates"] == 0
        assert body["total_leads"] == 0

    def test_overview_with_invalid_category(self, client, user):
        response = client.get("/api/dashboard/overview?category=salary", headers=user["headers"])
        assert response.status_code == 400

    def test_overview_requires_auth(self, client):
        assert client.get("/api/dashboard/overview").status_code == 401


# ---------------------------------------------------------------------------
# /dashboard/analytics
# ---------------------------------------------------------------------------


class TestAnalytics:
    def test_analytics_empty_database(self, client, user):
        response = client.get("/api/dashboard/analytics", headers=user["headers"])
        assert response.status_code == 200
        body = response.json()
        assert body["total_jobs"] == 0
        assert body["total_candidates"] == 0
        assert body["avg_ai_score"] == 0.0
        assert body["funnel"] == {
            "applied": 0,
            "screening": 0,
            "interview": 0,
            "shortlisted": 0,
            "hired": 0,
            "rejected": 0,
        }
        assert body["hiring_status_counts"] == {
            "strong_hire": 0,
            "hire": 0,
            "weak_hire": 0,
            "do_not_hire": 0,
        }
        assert body["interview_status_counts"] == {
            "in_process": 0,
            "completed": 0,
            "not_completed": 0,
        }
        assert body["score_distribution"] == [
            {"bucket": "0-49", "count": 0},
            {"bucket": "50-59", "count": 0},
            {"bucket": "60-69", "count": 0},
            {"bucket": "70-79", "count": 0},
            {"bucket": "80-89", "count": 0},
            {"bucket": "90-100", "count": 0},
        ]
        assert len(body["weekly_volume"]) == 6

    def test_analytics_aggregates_correctly(self, client, user):
        job1 = _create_job(client, user["headers"], company_name="Acme Corp", position="Backend Developer")
        job2 = _create_job(client, user["headers"], company_name="Globex", position="Data Engineer")
        worker1 = _create_worker(client, user["headers"], job1["id"], "Worker A")
        worker2 = _create_worker(client, user["headers"], job1["id"], "Worker B")
        worker3 = _create_worker(client, user["headers"], job2["id"], "Worker C")

        # Update some workers with different statuses and scores
        client.patch(
            f"/api/workers/{worker1['id']}",
            json={"hiring_status": "strong_hire", "interview_status": "completed", "ai_score": 95},
            headers=user["headers"],
        )
        client.patch(
            f"/api/workers/{worker2['id']}",
            json={"hiring_status": "hire", "interview_status": "in_process", "ai_score": 82},
            headers=user["headers"],
        )
        client.patch(
            f"/api/workers/{worker3['id']}",
            json={"hiring_status": "weak_hire", "interview_status": "not_completed", "ai_score": 65},
            headers=user["headers"],
        )

        body = client.get("/api/dashboard/analytics", headers=user["headers"]).json()

        assert body["total_jobs"] == 2
        assert body["total_candidates"] == 3
        assert body["avg_ai_score"] == 80.7  # (95 + 82 + 65) / 3

        # Hiring funnel
        assert body["funnel"]["applied"] == 3  # all are "new" by default
        assert body["funnel"]["screening"] == 0
        assert body["funnel"]["interview"] == 0
        assert body["funnel"]["shortlisted"] == 0
        assert body["funnel"]["hired"] == 0
        assert body["funnel"]["rejected"] == 0

        # Hiring status counts
        assert body["hiring_status_counts"]["strong_hire"] == 1
        assert body["hiring_status_counts"]["hire"] == 1
        assert body["hiring_status_counts"]["weak_hire"] == 1
        assert body["hiring_status_counts"]["do_not_hire"] == 0

        # Interview status counts
        assert body["interview_status_counts"]["in_process"] == 1
        assert body["interview_status_counts"]["completed"] == 1
        assert body["interview_status_counts"]["not_completed"] == 1

        # Score distribution
        score_dist = {d["bucket"]: d["count"] for d in body["score_distribution"]}
        assert score_dist["0-49"] == 0
        assert score_dist["50-59"] == 0
        assert score_dist["60-69"] == 1  # Worker C with 65
        assert score_dist["70-79"] == 0
        assert score_dist["80-89"] == 1  # Worker B with 82
        assert score_dist["90-100"] == 1  # Worker A with 95

    def test_analytics_requires_auth(self, client):
        assert client.get("/api/dashboard/analytics").status_code == 401

    def test_analytics_only_counts_own_data(self, client, user, other_user):
        _create_job(client, user["headers"], position="My Job")
        _create_worker(client, user["headers"], 1, "My Worker")

        body = client.get("/api/dashboard/analytics", headers=other_user["headers"]).json()
        assert body["total_jobs"] == 0
        assert body["total_candidates"] == 0
        assert body["funnel"]["applied"] == 0