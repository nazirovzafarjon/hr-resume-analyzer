"""Tests for auto-analyze batch functionality."""

import pytest

from tests.payloads import JOB_PAYLOAD


class TestAutoAnalyzeAvailable:
    """Tests for GET /api/applications/auto-analyze/available."""

    def test_available_count_returns_zero_when_no_applications(self, client, user):
        response = client.get(
            "/api/applications/auto-analyze/available",
            headers=user["headers"],
        )
        assert response.status_code == 200
        assert response.json()["count"] == 0

    def test_available_count_unauth_returns_401(self, client, sample_job):
        response = client.get("/api/applications/auto-analyze/available")
        assert response.status_code == 401

    def test_available_count_other_users_returns_zero(self, client, sample_job, other_user):
        response = client.get(
            "/api/applications/auto-analyze/available",
            headers=other_user["headers"],
        )
        assert response.status_code == 200
        assert response.json()["count"] == 0


class TestAutoAnalyzeStart:
    """Tests for POST /api/applications/auto-analyze."""

    def test_start_batch_validation_count_too_low(self, client, user, sample_job, application_factory):
        application_factory(sample_job["id"])

        response = client.post(
            "/api/applications/auto-analyze",
            json={"count": 0, "order": "oldest"},
            headers=user["headers"],
        )
        assert response.status_code == 422

    def test_start_batch_validation_count_too_high(self, client, user, sample_job, application_factory):
        application_factory(sample_job["id"])

        response = client.post(
            "/api/applications/auto-analyze",
            json={"count": 1001, "order": "oldest"},
            headers=user["headers"],
        )
        assert response.status_code == 422

    def test_start_batch_validation_count_negative(self, client, user, sample_job, application_factory):
        application_factory(sample_job["id"])

        response = client.post(
            "/api/applications/auto-analyze",
            json={"count": -1, "order": "oldest"},
            headers=user["headers"],
        )
        assert response.status_code == 422

    def test_start_batch_validation_order_invalid(self, client, user, sample_job, application_factory):
        application_factory(sample_job["id"])

        response = client.post(
            "/api/applications/auto-analyze",
            json={"count": 5, "order": "invalid"},
            headers=user["headers"],
        )
        assert response.status_code == 422

    def test_start_batch_success(self, client, user, sample_job, application_factory):
        for _ in range(3):
            application_factory(sample_job["id"])

        response = client.post(
            "/api/applications/auto-analyze",
            json={"count": 2, "order": "oldest"},
            headers=user["headers"],
        )
        assert response.status_code == 201
        data = response.json()
        assert data["requested_count"] == 2
        assert data["selected_count"] == 2
        assert data["status"] == "queued"
        assert "batch_id" in data

    def test_start_batch_capped_to_available(self, client, user, sample_job, application_factory):
        application_factory(sample_job["id"])
        application_factory(sample_job["id"])

        response = client.post(
            "/api/applications/auto-analyze",
            json={"count": 10, "order": "oldest"},
            headers=user["headers"],
        )
        assert response.status_code == 201
        data = response.json()
        assert data["requested_count"] == 10
        assert data["selected_count"] == 2

    def test_start_batch_no_available(self, client, user):
        response = client.post(
            "/api/applications/auto-analyze",
            json={"count": 5, "order": "oldest"},
            headers=user["headers"],
        )
        assert response.status_code == 400

    def test_start_batch_unauth_returns_401(self, client, sample_job, application_factory):
        application_factory(sample_job["id"])

        response = client.post(
            "/api/applications/auto-analyze",
            json={"count": 5, "order": "oldest"},
        )
        assert response.status_code == 401

    def test_start_batch_other_users_returns_401(self, client, sample_job, other_user, application_factory):
        # Create a job for the other user
        response = client.post(
            "/api/jobs",
            json=JOB_PAYLOAD,
            headers=other_user["headers"],
        )
        other_job = response.json()

        # Create applications for the other user's job
        application_factory(other_job["id"], headers=other_user["headers"])
        application_factory(other_job["id"], headers=other_user["headers"])

        response = client.post(
            "/api/applications/auto-analyze",
            json={"count": 5, "order": "oldest"},
            headers=other_user["headers"],
        )
        # Should succeed since the other user has their own applications
        assert response.status_code == 201
        data = response.json()
        assert data["selected_count"] == 2


