"""Tests for Celery notifications (email) and exports background tasks."""

from pathlib import Path
from unittest.mock import patch

from app.core.config import settings
from app.services.email import EmailDeliveryResult
from app.tasks.exports import generate_export_task
from app.tasks.notifications import send_email_task


def test_send_email_task_verification_code():
    """Verify send_email_task delivers verification code emails."""
    with patch(
        "app.services.email.send_verification_code_email",
        return_value=EmailDeliveryResult(success=True, message_id="msg_test_123"),
    ):
        result = send_email_task.apply(
            kwargs={
                "email_type": "verification_code",
                "recipient": "hr@example.com",
                "code": "123456",
            }
        ).result

    assert result["status"] == "delivered"
    assert result["recipient"] == "hr@example.com"
    assert result["message_id"] == "msg_test_123"


def test_send_email_task_unsupported_type():
    """Verify unsupported email type reports failure cleanly without raising."""
    result = send_email_task.apply(
        kwargs={
            "email_type": "non_existent_type",
            "recipient": "test@example.com",
        }
    ).result

    assert result["status"] == "unsupported_type"


def test_generate_export_task_xlsx(client, sample_application, db_session):
    """Verify generate_export_task generates XLSX files to shared volume."""
    result = generate_export_task.apply(
        kwargs={
            "resource": "applications",
            "filters": {},
            "columns": ["name", "email", "ai_score"],
            "format": "xlsx",
            "owner_id": None,
            "output_filename": "test_applications.xlsx",
        }
    ).result

    assert result["status"] == "completed"
    assert result["filename"] == "test_applications.xlsx"
    assert result["record_count"] >= 1
    assert result["file_size"] > 0

    export_file = Path(settings.UPLOAD_DIR) / "exports" / "test_applications.xlsx"
    assert export_file.exists()


def test_generate_export_task_pdf(client, sample_application, db_session):
    """Verify generate_export_task generates PDF files to shared volume."""
    result = generate_export_task.apply(
        kwargs={
            "resource": "applications",
            "filters": {},
            "columns": ["name", "email", "ai_score"],
            "format": "pdf",
            "owner_id": None,
            "output_filename": "test_applications.pdf",
        }
    ).result

    assert result["status"] == "completed"
    assert result["filename"] == "test_applications.pdf"
    assert result["record_count"] >= 1
    assert result["file_size"] > 0

    export_file = Path(settings.UPLOAD_DIR) / "exports" / "test_applications.pdf"
    assert export_file.exists()


def test_generate_export_task_invalid_resource(db_session):
    """Verify invalid resource type returns invalid_parameters."""
    result = generate_export_task.apply(
        kwargs={
            "resource": "non_existent_table",
            "filters": {},
            "columns": [],
            "format": "xlsx",
        }
    ).result

    assert result["status"] == "invalid_parameters"
