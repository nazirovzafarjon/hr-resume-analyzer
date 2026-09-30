"""Tests for the public application form feature.

Covers:

* HR endpoints: create job with form config, GET/PUT/publish/DELETE the
  configuration, ownership rules and validation errors.
* Public endpoints (no JWT): token retrieval, safe payload shape and
  server-side submission validation against the stored field config.
* Persistence: candidates (workers) created through the existing pipeline,
  structured answers stored, resume files saved with safe server names.
* Field normalisation: AI suggestions / defaults are data-only and constrained
  to the fixed field-type registry.
"""

import json
import uuid
from pathlib import Path

import pytest

from tests.payloads import JOB_PAYLOAD

from app.core.config import settings
from app.crud.application_response import get_response_by_worker
from app.schemas.application_form import (
    MAX_FIELDS,
    FormValidationError,
    normalise_application_fields,
    validate_application_form_fields,
)
from app.services.ai.job_analyzer import _parse_job_response

# ---------------------------------------------------------------------------
# Shared fixtures/helpers
# ---------------------------------------------------------------------------

DEFAULT_FIELDS = [
    {"label": "Full name", "type": "text", "required": True},
    {"label": "Email", "type": "email", "required": True},
    {"label": "Resume", "type": "file", "required": True},
]


def create_job_with_form(client, headers, fields=None):
    """Create a job with an application form through the API."""
    payload = dict(
        JOB_PAYLOAD, application_form={"fields": fields or DEFAULT_FIELDS}
    )
    response = client.post("/api/jobs", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def submit_application(client, token, values, files=None, headers=None):
    """Submit a public application (multipart)."""
    payload_files = {"values": (None, json.dumps(values))}
    if files:
        payload_files.update(files)
    return client.post(
        f"/api/public/applications/{token}/submit",
        files=payload_files,
        headers=headers,
    )


# ---------------------------------------------------------------------------
# HR: create job with application form
# ---------------------------------------------------------------------------


class TestCreateJobWithForm:
    def test_create_job_with_form_returns_public_token(self, client, user):
        job = create_job_with_form(client, user["headers"])
        form = job["application_form"]
        assert form["job_id"] == job["id"]
        assert len(form["public_token"]) >= 24
        assert [f["label"] for f in form["fields"]] == ["Full name", "Email", "Resume"]
        assert form["fields"][0]["type"] == "text"
        assert form["fields"][1]["type"] == "email"
        assert form["fields"][2]["type"] == "file"

    def test_create_job_without_form_has_no_application_form(self, client, user):
        response = client.post("/api/jobs", json=JOB_PAYLOAD, headers=user["headers"])
        assert response.status_code == 201
        assert response.json()["application_form"] is None

    def test_create_job_with_invalid_form_fails_and_keeps_no_job(self, client, user):
        payload = dict(
            JOB_PAYLOAD,
            application_form={"fields": [{"label": "", "type": "text"}]},
        )
        response = client.post("/api/jobs", json=payload, headers=user["headers"])
        assert response.status_code == 422
        # The job must not be left behind (atomic create).
        listing = client.get("/api/jobs", headers=user["headers"]).json()
        assert listing == []

    def test_create_job_form_unknown_type_rejected(self, client, user):
        payload = dict(
            JOB_PAYLOAD,
            application_form={"fields": [{"label": "X", "type": "html_embed"}]},
        )
        response = client.post("/api/jobs", json=payload, headers=user["headers"])
        assert response.status_code == 422

    def test_fields_persisted_in_submitted_order(self, client, user):
        fields = [
            {"label": "Portfolio", "type": "url", "required": False},
            {"label": "Full name", "type": "text", "required": True},
        ]
        job = create_job_with_form(client, user["headers"], fields)
        assert [f["label"] for f in job["application_form"]["fields"]] == [
            "Portfolio",
            "Full name",
        ]
        assert [f["order"] for f in job["application_form"]["fields"]] == [0, 1]

    def test_field_keys_generated_and_unique(self, client, user):
        fields = [
            {"label": "Full name", "type": "text", "required": False},
            {"label": "Full name", "type": "text", "required": False},
        ]
        job = create_job_with_form(client, user["headers"], fields)
        keys = [f["key"] for f in job["application_form"]["fields"]]
        assert keys[0] == "full_name"
        assert keys[1] != keys[0]
        assert len(set(keys)) == 2


# ---------------------------------------------------------------------------
# HR: application-form endpoints
# ---------------------------------------------------------------------------


class TestApplicationFormEndpoints:
    def test_get_application_form(self, client, user):
        job = create_job_with_form(client, user["headers"])
        response = client.get(
            f"/api/jobs/{job['id']}/application-form", headers=user["headers"]
        )
        assert response.status_code == 200
        assert response.json()["public_token"] == job["application_form"]["public_token"]

    def test_get_application_form_requires_auth(self, client, user):
        job = create_job_with_form(client, user["headers"])
        response = client.get(f"/api/jobs/{job['id']}/application-form")
        assert response.status_code == 401

    def test_get_application_form_other_user_404(self, client, user, other_user):
        job = create_job_with_form(client, user["headers"])
        response = client.get(
            f"/api/jobs/{job['id']}/application-form", headers=other_user["headers"]
        )
        assert response.status_code == 404

    def test_get_application_form_without_config_404(self, client, user):
        response = client.post("/api/jobs", json=JOB_PAYLOAD, headers=user["headers"])
        job_id = response.json()["id"]
        response = client.get(
            f"/api/jobs/{job_id}/application-form", headers=user["headers"]
        )
        assert response.status_code == 404

    def test_put_updates_fields_and_preserves_token(self, client, user):
        job = create_job_with_form(client, user["headers"])
        token = job["application_form"]["public_token"]
        new_fields = [
            {
                "label": "Preferred work model",
                "type": "select",
                "required": True,
                "options": ["Remote", "Hybrid", "On-site"],
            },
        ]
        response = client.put(
            f"/api/jobs/{job['id']}/application-form",
            json={"fields": new_fields},
            headers=user["headers"],
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["public_token"] == token  # token preserved
        assert body["fields"][0]["options"] == ["Remote", "Hybrid", "On-site"]

        # Persistence check.
        refetched = client.get(
            f"/api/jobs/{job['id']}/application-form", headers=user["headers"]
        ).json()
        assert refetched["fields"][0]["label"] == "Preferred work model"

    def test_put_creates_form_when_missing(self, client, user):
        response = client.post("/api/jobs", json=JOB_PAYLOAD, headers=user["headers"])
        job_id = response.json()["id"]
        response = client.put(
            f"/api/jobs/{job_id}/application-form",
            json={"fields": DEFAULT_FIELDS},
            headers=user["headers"],
        )
        assert response.status_code == 200
        assert response.json()["public_token"]

    def test_put_preserves_field_ids_so_links_stay_stable(self, client, user):
        job = create_job_with_form(client, user["headers"])
        field_id = job["application_form"]["fields"][0]["id"]
        response = client.put(
            f"/api/jobs/{job['id']}/application-form",
            json={"fields": job["application_form"]["fields"]},
            headers=user["headers"],
        )
        assert response.status_code == 200
        assert response.json()["fields"][0]["id"] == field_id

    def test_publish_keeps_token_by_default(self, client, user):
        job = create_job_with_form(client, user["headers"])
        token = job["application_form"]["public_token"]
        response = client.post(
            f"/api/jobs/{job['id']}/application-form/publish",
            json={"regenerate_token": False},
            headers=user["headers"],
        )
        assert response.status_code == 200
        assert response.json()["public_token"] == token

    def test_publish_regenerates_token_and_kills_old_link(self, client, user):
        job = create_job_with_form(client, user["headers"])
        old_token = job["application_form"]["public_token"]
        response = client.post(
            f"/api/jobs/{job['id']}/application-form/publish",
            json={"regenerate_token": True},
            headers=user["headers"],
        )
        assert response.status_code == 200
        new_token = response.json()["public_token"]
        assert new_token != old_token
        assert client.get(f"/api/public/applications/{old_token}").status_code == 404
        assert client.get(f"/api/public/applications/{new_token}").status_code == 200

    def test_publish_without_form_404(self, client, user):
        response = client.post("/api/jobs", json=JOB_PAYLOAD, headers=user["headers"])
        job_id = response.json()["id"]
        response = client.post(
            f"/api/jobs/{job_id}/application-form/publish", headers=user["headers"]
        )
        assert response.status_code == 404

    def test_publish_other_user_404(self, client, user, other_user):
        job = create_job_with_form(client, user["headers"])
        response = client.post(
            f"/api/jobs/{job['id']}/application-form/publish",
            headers=other_user["headers"],
        )
        assert response.status_code == 404

    def test_delete_resets_config_and_invalidates_link(self, client, user):
        job = create_job_with_form(client, user["headers"])
        token = job["application_form"]["public_token"]
        response = client.delete(
            f"/api/jobs/{job['id']}/application-form", headers=user["headers"]
        )
        assert response.status_code == 204
        assert (
            client.get(
                f"/api/jobs/{job['id']}/application-form", headers=user["headers"]
            ).status_code
            == 404
        )
        assert client.get(f"/api/public/applications/{token}").status_code == 404

    def test_job_response_embeds_application_form(self, client, user):
        job = create_job_with_form(client, user["headers"])
        fetched = client.get(
            f"/api/jobs/{job['id']}", headers=user["headers"]
        ).json()
        assert (
            fetched["application_form"]["public_token"]
            == job["application_form"]["public_token"]
        )


# ---------------------------------------------------------------------------
# HR: validation errors (publish safety)
# ---------------------------------------------------------------------------


class TestFormValidationErrors:
    def _put(self, client, user, fields):
        job = create_job_with_form(client, user["headers"])
        return client.put(
            f"/api/jobs/{job['id']}/application-form",
            json={"fields": fields},
            headers=user["headers"],
        )

    def test_empty_fields_rejected(self, client, user):
        response = self._put(client, user, [])
        assert response.status_code == 422
        assert "at least one" in response.json()["detail"].lower()

    def test_blank_label_rejected(self, client, user):
        response = self._put(client, user, [{"label": "  ", "type": "text"}])
        assert response.status_code == 422
        assert "label" in response.json()["detail"].lower()

    def test_unknown_type_rejected(self, client, user):
        response = self._put(client, user, [{"label": "Question", "type": "html"}])
        assert response.status_code == 422
        assert "unsupported type" in response.json()["detail"].lower()

    def test_select_without_options_rejected(self, client, user):
        response = self._put(client, user, [{"label": "Choice", "type": "select"}])
        assert response.status_code == 422
        assert "option" in response.json()["detail"].lower()

    def test_select_with_empty_option_rejected(self, client, user):
        response = self._put(
            client,
            user,
            [{"label": "Choice", "type": "select", "options": ["A", "   "]}],
        )
        assert response.status_code == 422

    def test_too_many_fields_rejected(self, client, user):
        fields = [
            {"label": f"Question {i}", "type": "text"} for i in range(MAX_FIELDS + 1)
        ]
        response = self._put(client, user, fields)
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Public: retrieve application by token (no JWT)
# ---------------------------------------------------------------------------


class TestPublicRetrieve:
    def test_retrieve_without_authentication(self, client, user):
        job = create_job_with_form(client, user["headers"])
        token = job["application_form"]["public_token"]
        response = client.get(f"/api/public/applications/{token}")
        assert response.status_code == 200

    def test_payload_contains_only_candidate_safe_data(self, client, user):
        job = create_job_with_form(client, user["headers"])
        token = job["application_form"]["public_token"]
        body = client.get(f"/api/public/applications/{token}").json()

        assert body["job"]["company_name"] == "Acme Corp"
        assert body["job"]["position"] == "Backend Developer"
        assert len(body["fields"]) == 3
        assert {f["type"] for f in body["fields"]} == {"text", "email", "file"}

        # No private data leaks to the candidate.
        assert "owner_id" not in body["job"]
        assert "leads_count" not in body["job"]
        assert "public_id" not in body["job"]
        assert "id" not in body["job"]

    def test_invalid_token_404_with_safe_message(self, client, user):
        create_job_with_form(client, user["headers"])
        response = client.get("/api/public/applications/not-a-real-token")
        assert response.status_code == 404
        assert response.json()["detail"] == "This application link is no longer available."

    def test_numeric_id_does_not_work_as_token(self, client, user):
        job = create_job_with_form(client, user["headers"])
        response = client.get(f"/api/public/applications/{job['id']}")
        assert response.status_code == 404

    def test_random_uuid_does_not_work_as_token(self, client):
        response = client.get(f"/api/public/applications/{uuid.uuid4()}")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Public: submit application
# ---------------------------------------------------------------------------


class TestPublicSubmit:
    def test_submit_success_creates_candidate_and_stores_answers(
        self, client, user, db_session
    ):
        job = create_job_with_form(client, user["headers"])
        token = job["application_form"]["public_token"]
        fields = job["application_form"]["fields"]
        name_id, email_id, resume_id = [f["id"] for f in fields]

        response = submit_application(
            client,
            token,
            {name_id: "Jane Doe", email_id: "Jane@Example.com", resume_id: ""},
            files={resume_id: ("my-resume.pdf", b"%PDF-fake", "application/pdf")},
        )
        assert response.status_code == 201, response.text
        assert response.json() == {"status": "received"}

        # Candidate created through the existing worker pipeline.
        workers = client.get(
            f"/api/workers?job_id={job['id']}", headers=user["headers"]
        ).json()
        assert len(workers) == 1
        worker = workers[0]
        assert worker["name"] == "Jane Doe"
        assert worker["email"] == "jane@example.com"  # normalised
        assert worker["resume_path"].startswith("resumes/")  # safe server name
        assert worker["resume_path"].endswith(".pdf")

        # The uploaded file exists on disk under a generated name.
        from app.core.config import settings

        stored = Path(settings.UPLOAD_DIR) / worker["resume_path"]
        assert stored.exists()
        assert stored.name != "my-resume.pdf"  # never trusts the filename
        assert stored.read_bytes() == b"%PDF-fake"

        # Structured answers stored next to the candidate.
        answers = get_response_by_worker(db_session, worker["id"])
        assert answers is not None
        by_field = {a["field_id"]: a for a in answers.responses}
        assert by_field[name_id]["value"] == "Jane Doe"
        assert by_field[email_id]["value"] == "jane@example.com"
        assert by_field[resume_id]["value"] == worker["resume_path"]

        # Job lead count incremented.
        fetched = client.get(f"/api/jobs/{job['id']}", headers=user["headers"]).json()
        assert fetched["leads_count"] == 1

    def test_submit_with_select_and_multiselect(self, client, user):
        fields = [
            {"label": "Full name", "type": "text", "required": True},
            {
                "label": "Work model",
                "type": "select",
                "required": True,
                "options": ["Remote", "Hybrid", "On-site"],
            },
            {
                "label": "Skills",
                "type": "multi_select",
                "required": False,
                "options": ["Python", "SQL", "Docker"],
            },
        ]
        job = create_job_with_form(client, user["headers"], fields)
        token = job["application_form"]["public_token"]
        f_name, f_select, f_multi = [f["id"] for f in job["application_form"]["fields"]]

        response = submit_application(
            client,
            token,
            {f_name: "Jane", f_select: "Hybrid", f_multi: ["Docker", "Python"]},
        )
        assert response.status_code == 201, response.text

    def test_missing_required_field_rejected(self, client, user):
        job = create_job_with_form(client, user["headers"])
        token = job["application_form"]["public_token"]
        fields = job["application_form"]["fields"]
        values = {fields[0]["id"]: "Jane"}  # email + resume missing
        response = submit_application(client, token, values)
        assert response.status_code == 422
        assert "required fields" in response.json()["detail"].lower()

    def test_unknown_field_id_rejected(self, client, user):
        job = create_job_with_form(client, user["headers"])
        token = job["application_form"]["public_token"]
        fields = job["application_form"]["fields"]
        values = {f["id"]: "x" for f in fields}
        values["fld_unknown000"] = "injected"
        response = submit_application(client, token, values)
        assert response.status_code == 422

    def test_invalid_select_option_rejected(self, client, user):
        fields = [
            {"label": "Full name", "type": "text", "required": True},
            {
                "label": "Work model",
                "type": "select",
                "required": True,
                "options": ["Remote", "On-site"],
            },
        ]
        job = create_job_with_form(client, user["headers"], fields)
        token = job["application_form"]["public_token"]
        f_name, f_select = [f["id"] for f in job["application_form"]["fields"]]

        response = submit_application(client, token, {f_name: "Jane", f_select: "Mars"})
        assert response.status_code == 422
        assert "option" in response.json()["detail"].lower()

    def test_invalid_multiselect_option_rejected(self, client, user):
        fields = [
            {"label": "Full name", "type": "text", "required": True},
            {
                "label": "Skills",
                "type": "multi_select",
                "required": False,
                "options": ["Python", "SQL"],
            },
        ]
        job = create_job_with_form(client, user["headers"], fields)
        token = job["application_form"]["public_token"]
        f_name, f_multi = [f["id"] for f in job["application_form"]["fields"]]

        response = submit_application(
            client, token, {f_name: "Jane", f_multi: ["Python", "COBOL"]}
        )
        assert response.status_code == 422

    def test_invalid_email_rejected(self, client, user):
        job = create_job_with_form(client, user["headers"])
        token = job["application_form"]["public_token"]
        fields = job["application_form"]["fields"]
        values = {fields[0]["id"]: "Jane", fields[1]["id"]: "not-an-email"}
        response = submit_application(client, token, values)
        assert response.status_code == 422
        assert "email" in response.json()["detail"].lower()

    def test_invalid_number_rejected(self, client, user):
        fields = [{"label": "Years of experience", "type": "number", "required": True}]
        job = create_job_with_form(client, user["headers"], fields)
        token = job["application_form"]["public_token"]
        (f_number,) = [f["id"] for f in job["application_form"]["fields"]]

        response = submit_application(client, token, {f_number: "three years"})
        assert response.status_code == 422
        assert "number" in response.json()["detail"].lower()

    def test_invalid_date_rejected(self, client, user):
        fields = [{"label": "Start date", "type": "date", "required": True}]
        job = create_job_with_form(client, user["headers"], fields)
        token = job["application_form"]["public_token"]
        (f_date,) = [f["id"] for f in job["application_form"]["fields"]]

        response = submit_application(client, token, {f_date: "31-02-2026"})
        assert response.status_code == 422
        assert "date" in response.json()["detail"].lower()

    def test_invalid_url_rejected(self, client, user):
        fields = [{"label": "Portfolio", "type": "url", "required": True}]
        job = create_job_with_form(client, user["headers"], fields)
        token = job["application_form"]["public_token"]
        (f_url,) = [f["id"] for f in job["application_form"]["fields"]]

        response = submit_application(client, token, {f_url: "not a url"})
        assert response.status_code == 422

    def test_required_checkbox_must_be_checked(self, client, user):
        fields = [
            {"label": "Full name", "type": "text", "required": True},
            {"label": "I accept the terms", "type": "checkbox", "required": True},
        ]
        job = create_job_with_form(client, user["headers"], fields)
        token = job["application_form"]["public_token"]
        f_name, f_check = [f["id"] for f in job["application_form"]["fields"]]

        response = submit_application(client, token, {f_name: "Jane", f_check: False})
        assert response.status_code == 422
        assert "checked" in response.json()["detail"].lower()

        response = submit_application(client, token, {f_name: "Jane", f_check: True})
        assert response.status_code == 201

    def test_file_wrong_type_rejected(self, client, user):
        job = create_job_with_form(client, user["headers"])
        token = job["application_form"]["public_token"]
        fields = job["application_form"]["fields"]
        values = {
            fields[0]["id"]: "Jane",
            fields[1]["id"]: "jane@example.com",
        }

        response = submit_application(
            client,
            token,
            values,
            files={fields[2]["id"]: ("evil.exe", b"MZ", "application/x-msdownload")},
        )
        assert response.status_code == 422
        assert "file type" in response.json()["detail"].lower()

    def test_file_too_large_rejected(self, client, user):
        job = create_job_with_form(client, user["headers"])
        token = job["application_form"]["public_token"]
        fields = job["application_form"]["fields"]
        values = {
            fields[0]["id"]: "Jane",
            fields[1]["id"]: "jane@example.com",
        }
        big = b"x" * (11 * 1024 * 1024)  # 11MB

        response = submit_application(
            client,
            token,
            values,
            files={fields[2]["id"]: ("big.pdf", big, "application/pdf")},
        )
        assert response.status_code == 422
        assert "10mb" in response.json()["detail"].lower()

    def test_missing_required_file_rejected(self, client, user):
        job = create_job_with_form(client, user["headers"])
        token = job["application_form"]["public_token"]
        fields = job["application_form"]["fields"]
        values = {
            fields[0]["id"]: "Jane",
            fields[1]["id"]: "jane@example.com",
        }
        response = submit_application(client, token, values)
        assert response.status_code == 422

    def test_malformed_values_json_rejected(self, client, user):
        job = create_job_with_form(client, user["headers"])
        token = job["application_form"]["public_token"]
        response = client.post(
            f"/api/public/applications/{token}/submit",
            files={"values": (None, "{not json")},
        )
        assert response.status_code == 422

    def test_non_multipart_submission_rejected(self, client, user):
        job = create_job_with_form(client, user["headers"])
        token = job["application_form"]["public_token"]
        response = client.post(
            f"/api/public/applications/{token}/submit", json={"values": {}}
        )
        assert response.status_code == 422

    def test_identity_fallback_without_name_or_email_field(self, client, user):
        fields = [{"label": "Motivation", "type": "textarea", "required": True}]
        job = create_job_with_form(client, user["headers"], fields)
        token = job["application_form"]["public_token"]
        (f_motivation,) = [f["id"] for f in job["application_form"]["fields"]]

        response = submit_application(client, token, {f_motivation: "I want this job."})
        assert response.status_code == 201

        workers = client.get(
            f"/api/workers?job_id={job['id']}", headers=user["headers"]
        ).json()
        assert len(workers) == 1
        assert workers[0]["name"] == "Anonymous candidate"
        assert workers[0]["email"].endswith("@candidates.local")


# ---------------------------------------------------------------------------
# Duplicate submission guard
# ---------------------------------------------------------------------------


class TestDuplicateSubmissionGuard:
    def test_same_email_within_window_rejected(self, client, user):
        job = create_job_with_form(client, user["headers"])
        token = job["application_form"]["public_token"]
        fields = job["application_form"]["fields"]
        values = {
            fields[0]["id"]: "Jane",
            fields[1]["id"]: "jane@example.com",
        }
        files = {fields[2]["id"]: ("r.pdf", b"%PDF", "application/pdf")}

        first = submit_application(client, token, values, files=files)
        assert first.status_code == 201

        second = submit_application(client, token, values, files=files)
        assert second.status_code == 409
        assert "already" in second.json()["detail"].lower()

    def test_rejected_duplicate_leaves_no_resume_file(self, client, user):
        job = create_job_with_form(client, user["headers"])
        token = job["application_form"]["public_token"]
        fields = job["application_form"]["fields"]
        values = {fields[0]["id"]: "Jane", fields[1]["id"]: "jane@example.com"}
        files = {fields[2]["id"]: ("r.pdf", b"%PDF", "application/pdf")}
        resumes = Path(settings.UPLOAD_DIR) / "resumes"

        assert submit_application(client, token, values, files=files).status_code == 201
        stored_before = set(resumes.iterdir())

        second = submit_application(client, token, values, files=files)

        assert second.status_code == 409
        assert set(resumes.iterdir()) == stored_before

    def test_failed_save_removes_files_already_written(self, client, user, monkeypatch):
        fields = [
            {"label": "Full name", "type": "text", "required": True},
            {"label": "Email", "type": "email", "required": True},
            {"label": "Resume", "type": "file", "required": True},
            {"label": "Cover letter", "type": "file", "required": True},
        ]
        job = create_job_with_form(client, user["headers"], fields=fields)
        token = job["application_form"]["public_token"]
        stored = job["application_form"]["fields"]
        resumes = Path(settings.UPLOAD_DIR) / "resumes"
        resumes.mkdir(parents=True, exist_ok=True)
        stored_before = set(resumes.iterdir())

        from app.crud import worker as worker_crud

        def boom(*args, **kwargs):
            raise RuntimeError("database down")

        monkeypatch.setattr(worker_crud, "create_worker", boom)
        with pytest.raises(RuntimeError):
            submit_application(
                client,
                token,
                {stored[0]["id"]: "Jane", stored[1]["id"]: "jane@example.com"},
                files={
                    stored[2]["id"]: ("r.pdf", b"%PDF", "application/pdf"),
                    stored[3]["id"]: ("c.txt", b"hello", "text/plain"),
                },
            )

        assert set(resumes.iterdir()) == stored_before

    def test_different_email_allowed(self, client, user):
        job = create_job_with_form(client, user["headers"])
        token = job["application_form"]["public_token"]
        fields = job["application_form"]["fields"]
        files = {fields[2]["id"]: ("r.pdf", b"%PDF", "application/pdf")}

        first = submit_application(
            client,
            token,
            {fields[0]["id"]: "Jane", fields[1]["id"]: "jane@example.com"},
            files=files,
        )
        second = submit_application(
            client,
            token,
            {fields[0]["id"]: "John", fields[1]["id"]: "john@example.com"},
            files=files,
        )
        assert first.status_code == 201
        assert second.status_code == 201


# ---------------------------------------------------------------------------
# Field normalisation (AI suggestions / defaults — data only, never UI)
# ---------------------------------------------------------------------------


class TestNormaliseApplicationFields:
    def test_drops_unknown_field_types(self):
        raw = [
            {"label": "Name", "type": "text"},
            {"label": "Evil", "type": "html_embed"},
            {"label": "Also evil", "type": "javascript"},
        ]
        normalised = normalise_application_fields(raw)
        assert [f["label"] for f in normalised] == ["Name"]
        assert normalised[0]["type"] == "text"

    def test_drops_blank_labels_and_non_dicts(self):
        raw = [
            {"label": "   ", "type": "text"},
            "just a string",
            {"type": "text"},  # no label
            {"label": "OK", "type": "text"},
        ]
        normalised = normalise_application_fields(raw)
        assert [f["label"] for f in normalised] == ["OK"]

    def test_drops_select_without_options(self):
        raw = [{"label": "Choice", "type": "select", "options": []}]
        assert normalise_application_fields(raw) == []

    def test_assigns_sequential_order_and_ids(self):
        raw = [
            {"label": "A", "type": "text"},
            {"label": "B", "type": "text"},
        ]
        normalised = normalise_application_fields(raw)
        assert [f["order"] for f in normalised] == [0, 1]
        assert all(f["id"].startswith("fld_") for f in normalised)
        assert len({f["id"] for f in normalised}) == 2

    def test_deduplicates_keys(self):
        raw = [
            {"label": "Full name", "type": "text"},
            {"label": "Full name", "type": "text"},
        ]
        keys = [f["key"] for f in normalise_application_fields(raw)]
        assert len(set(keys)) == 2

    def test_caps_number_of_fields(self):
        raw = [{"label": f"Q{i}", "type": "text"} for i in range(MAX_FIELDS + 10)]
        assert len(normalise_application_fields(raw)) == MAX_FIELDS

    def test_non_list_input_returns_empty(self):
        assert normalise_application_fields(None) == []
        assert normalise_application_fields("nope") == []


class TestValidateApplicationFormFields:
    def test_valid_fields_returned_as_plain_dicts(self):
        raw = [
            {"label": "Full name", "type": "text", "required": True},
            {"label": "Work model", "type": "select", "options": ["Remote"]},
        ]
        fields = validate_application_form_fields(raw)
        assert fields[0]["key"] == "full_name"
        assert fields[1]["options"] == ["Remote"]
        assert [f["order"] for f in fields] == [0, 1]

    def test_empty_form_raises(self):
        with pytest.raises(FormValidationError):
            validate_application_form_fields([])

    def test_blank_label_raises(self):
        with pytest.raises(FormValidationError):
            validate_application_form_fields([{"label": " ", "type": "text"}])

    def test_unknown_type_raises(self):
        with pytest.raises(FormValidationError):
            validate_application_form_fields([{"label": "X", "type": "google_form"}])

    def test_select_without_options_raises(self):
        with pytest.raises(FormValidationError):
            validate_application_form_fields([{"label": "X", "type": "select"}])

    def test_duplicate_option_raises(self):
        with pytest.raises(FormValidationError):
            validate_application_form_fields(
                [{"label": "X", "type": "select", "options": ["A", "A"]}]
            )

    def test_existing_ids_and_keys_are_preserved(self):
        raw = [{"id": "fld_custom", "key": "my_key", "label": "X", "type": "text"}]
        fields = validate_application_form_fields(raw)
        assert fields[0]["id"] == "fld_custom"
        assert fields[0]["key"] == "my_key"


class TestAIApplicationFieldSuggestions:
    """AI output is normalised to data against the fixed registry."""

    def test_parse_response_normalises_ai_field_suggestions(self):
        raw = {
            "company_name": "Acme",
            "position": "Dev",
            "description": "",
            "required_skills": "Python",
            "required_experience": "3+ years",
            "application_fields": [
                {"label": "Full name", "type": "text", "required": True},
                {"label": "Hacked", "type": "<script>embed</script>", "required": False},
                {"label": "Choice", "type": "select", "options": ["A", "B"]},
            ],
        }
        result = _parse_job_response(json.dumps(raw))
        assert result.application_fields is not None
        labels = [f["label"] for f in result.application_fields]
        assert labels == ["Full name", "Choice"]
        assert result.application_fields[0]["type"] == "text"
        assert result.application_fields[1]["type"] == "select"

    def test_parse_response_without_fields_returns_none(self):
        raw = {
            "company_name": "Acme",
            "position": "Dev",
            "description": "",
            "required_skills": "Python",
            "required_experience": "",
        }
        result = _parse_job_response(json.dumps(raw))
        assert result.application_fields is None

    def test_parse_response_all_garbage_fields_returns_none(self):
        raw = {
            "company_name": "Acme",
            "position": "Dev",
            "description": "",
            "required_skills": "",
            "required_experience": "",
            "application_fields": [{"label": "X", "type": "iframe"}],
        }
        result = _parse_job_response(json.dumps(raw))
        assert result.application_fields is None
