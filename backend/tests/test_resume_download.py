"""Tests for the protected CV endpoint (GET /api/applications/{id}/resume)."""

from pathlib import Path
from urllib.parse import unquote
from uuid import uuid4

import pytest

from app.core.config import settings
from tests.payloads import APPLICATION_PAYLOAD

PDF_BYTES = b"%PDF-1.4\n% test resume\n"


def _resumes_dir() -> Path:
    directory = Path(settings.UPLOAD_DIR) / "resumes"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _stored_resume(suffix: str = ".pdf", content: bytes = PDF_BYTES) -> str:
    """Write a resume the way uploads do and return its stored resume_path."""
    name = f"{uuid4().hex}{suffix}"
    (_resumes_dir() / name).write_bytes(content)
    return f"resumes/{name}"


def _application_with_resume(application_factory, job_id, resume_path, name="Jane Doe"):
    response = application_factory(
        job_id, payload={**APPLICATION_PAYLOAD, "name": name, "resume_path": resume_path}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _download_name(response) -> str:
    """Filename from Content-Disposition (plain or RFC 5987 ``filename*``)."""
    disposition = response.headers["content-disposition"]
    if "filename*=utf-8''" in disposition:
        return unquote(disposition.split("filename*=utf-8''", 1)[1])
    return disposition.split('filename="', 1)[1].rstrip('"')


def _resume_url(application_id, download=False):
    return f"/api/applications/{application_id}/resume" + ("?download=true" if download else "")


class TestViewAndDownload:
    def test_owner_views_pdf_inline(self, client, user, sample_job, application_factory):
        application_id = _application_with_resume(application_factory, sample_job["id"], _stored_resume())

        response = client.get(_resume_url(application_id), headers=user["headers"])

        assert response.status_code == 200
        assert response.content == PDF_BYTES
        assert response.headers["content-type"] == "application/pdf"
        assert response.headers["content-disposition"].startswith("inline")
        assert _download_name(response) == "Jane Doe - CV.pdf"
        assert response.headers["cache-control"] == "private, no-store"
        assert response.headers["x-content-type-options"] == "nosniff"

    def test_owner_downloads_as_attachment(self, client, user, sample_job, application_factory):
        application_id = _application_with_resume(application_factory, sample_job["id"], _stored_resume(".docx"))

        response = client.get(_resume_url(application_id, download=True), headers=user["headers"])

        assert response.status_code == 200
        assert response.headers["content-disposition"].startswith("attachment")
        assert response.headers["content-type"].startswith(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

    def test_download_name_never_uses_unsafe_characters(
        self, client, user, sample_job, application_factory
    ):
        application_id = _application_with_resume(
            application_factory, sample_job["id"], _stored_resume(), name='../"evil"/name'
        )

        response = client.get(_resume_url(application_id, download=True), headers=user["headers"])

        name = _download_name(response)
        assert name == "evilname - CV.pdf"
        assert "/" not in name and '"' not in name

    def test_detail_response_points_to_the_protected_endpoint(
        self, client, user, sample_job, application_factory
    ):
        stored = _stored_resume()
        application_id = _application_with_resume(application_factory, sample_job["id"], stored)

        body = client.get(f"/api/applications/{application_id}", headers=user["headers"]).json()

        assert body["resume_url"] == f"/applications/{application_id}/resume"
        assert settings.UPLOAD_DIR not in str(body)


class TestAccessControl:
    def test_unauthenticated_request_is_rejected(self, client, sample_job, application_factory):
        application_id = _application_with_resume(application_factory, sample_job["id"], _stored_resume())

        assert client.get(_resume_url(application_id)).status_code == 401

    def test_other_users_cv_looks_like_a_missing_application(
        self, client, sample_job, application_factory, other_user
    ):
        application_id = _application_with_resume(application_factory, sample_job["id"], _stored_resume())

        response = client.get(_resume_url(application_id), headers=other_user["headers"])

        assert response.status_code == 404
        assert response.json() == {"detail": "Application not found"}

    def test_unknown_application_returns_404(self, client, user):
        assert client.get(_resume_url(999999), headers=user["headers"]).status_code == 404

    def test_resumes_are_no_longer_public_static_files(
        self, client, sample_job, application_factory
    ):
        stored = _stored_resume()
        _application_with_resume(application_factory, sample_job["id"], stored)

        assert client.get(f"/uploads/{stored}").status_code == 404


class TestMissingOrUnsafeFiles:
    def test_application_without_cv(self, client, user, sample_job, application_factory):
        application_id = _application_with_resume(application_factory, sample_job["id"], "")

        response = client.get(_resume_url(application_id), headers=user["headers"])

        assert response.status_code == 404
        assert response.json()["detail"] == "No CV is available for this application."

    def test_file_missing_on_disk(self, client, user, sample_job, application_factory):
        application_id = _application_with_resume(
            application_factory, sample_job["id"], f"resumes/{uuid4().hex}.pdf"
        )

        response = client.get(_resume_url(application_id), headers=user["headers"])

        assert response.status_code == 404
        assert response.json()["detail"] == "The CV file could not be found."

    @pytest.mark.parametrize(
        "resume_path",
        [
            "resumes/../../.env",
            "../.env",
            "resumes/../profile/avatar.pdf",
            "/etc/passwd",
            "/resumes/x.pdf",
            "resumes\\..\\..\\app\\main.py",
            "https://example.com/cv.pdf",
            "resumes/cv.exe",
            "profile/avatar.pdf",
        ],
    )
    def test_path_traversal_and_foreign_paths_are_rejected(
        self, client, user, sample_job, application_factory, resume_path
    ):
        profile_dir = Path(settings.UPLOAD_DIR) / "profile"
        profile_dir.mkdir(parents=True, exist_ok=True)
        (profile_dir / "avatar.pdf").write_bytes(PDF_BYTES)
        (_resumes_dir() / "cv.exe").write_bytes(b"MZ")
        application_id = _application_with_resume(application_factory, sample_job["id"], resume_path)

        response = client.get(_resume_url(application_id), headers=user["headers"])

        assert response.status_code == 404
        assert b"MZ" not in response.content
        assert b"PDF" not in response.content

    def test_symlink_out_of_the_resumes_folder_is_rejected(
        self, client, user, sample_job, application_factory, tmp_path
    ):
        secret = tmp_path / "secret.pdf"
        secret.write_bytes(b"%PDF secret outside uploads")
        link_name = f"{uuid4().hex}.pdf"
        (_resumes_dir() / link_name).symlink_to(secret)
        application_id = _application_with_resume(
            application_factory, sample_job["id"], f"resumes/{link_name}"
        )

        response = client.get(_resume_url(application_id), headers=user["headers"])

        assert response.status_code == 404
        assert b"secret" not in response.content
