"""Tests for the Universal Export system.

Tests authentication, ownership, filtering, column validation, and file generation.
"""

import io
from datetime import datetime, date, timedelta

import pytest
from openpyxl import load_workbook
from PyPDF2 import PdfReader
from docx import Document

from app.models.application import Application, ApplicationStatus, AnalysisStatus, HiringStatus
from app.models.interview import Interview, InterviewStatus
from app.models.job import Job


@pytest.fixture
def sample_jobs(client, user):
    """Create sample jobs for testing."""
    jobs_data = [
        {
            "company_name": "Unicon Soft",
            "position": "Backend Developer",
            "description": "Senior backend developer position",
            "required_skills": "Python, FastAPI, PostgreSQL",
            "required_experience": "3+ years",
        },
        {
            "company_name": "TechCorp",
            "position": "Frontend Developer",
            "description": "React developer needed",
            "required_skills": "React, TypeScript, CSS",
            "required_experience": "2+ years",
        },
    ]
    
    created_jobs = []
    for job_data in jobs_data:
        response = client.post("/api/jobs", json=job_data, headers=user["headers"])
        assert response.status_code == 201
        created_jobs.append(response.json())
    
    return created_jobs


@pytest.fixture
def sample_applications(client, sample_jobs, user, db_session):
    """Create sample applications for testing."""
    job_id = sample_jobs[0]["id"]
    
    apps = [
        Application(
            job_id=job_id,
            name="John Doe",
            email="john@example.com",
            resume_path="resumes/john.pdf",
            ai_score=85.5,
            application_status=ApplicationStatus.SHORTLISTED,
            analysis_status=AnalysisStatus.COMPLETED,
            hiring_status=HiringStatus.HIRE,
            submitted_at=datetime.now() - timedelta(days=2),
        ),
        Application(
            job_id=job_id,
            name="Jane Smith",
            email="jane@example.com",
            resume_path="resumes/jane.pdf",
            ai_score=92.0,
            application_status=ApplicationStatus.INTERVIEW,
            analysis_status=AnalysisStatus.COMPLETED,
            hiring_status=HiringStatus.STRONG_HIRE,
            candidate_at=datetime.now() - timedelta(days=1),
            submitted_at=datetime.now() - timedelta(days=3),
        ),
        Application(
            job_id=job_id,
            name="Bob Johnson",
            email="bob@example.com",
            resume_path="resumes/bob.pdf",
            ai_score=70.0,
            application_status=ApplicationStatus.NEW,
            analysis_status=AnalysisStatus.PENDING,
            hiring_status=HiringStatus.WEAK_HIRE,
            submitted_at=datetime.now() - timedelta(days=1),
        ),
    ]
    
    db_session.add_all(apps)
    db_session.commit()
    for app in apps:
        db_session.refresh(app)
    
    return apps


@pytest.fixture
def sample_interviews(db_session, sample_applications, user):
    """Create sample interviews for testing."""
    candidate = sample_applications[1]  # Jane is a candidate
    
    interview = Interview(
        candidate_id=candidate.id,
        hr_id=user["id"],
        interviewer="Tech Lead",
        scheduled_at=datetime.now() + timedelta(days=2),
        duration_minutes=60,
        status=InterviewStatus.UPCOMING,
        meeting_link="https://zoom.us/j/123456",
    )
    
    db_session.add(interview)
    db_session.commit()
    db_session.refresh(interview)
    
    return [interview]


class TestExportAuthentication:
    """Test authentication and authorization for exports."""
    
    def test_unauthenticated_request_returns_401(self, client):
        """Unauthenticated export requests should return 401."""
        response = client.post(
            "/api/exports",
            json={
                "resource": "jobs",
                "filters": {},
                "columns": ["company", "position"],
                "format": "xlsx",
            },
        )
        assert response.status_code == 401
    
    def test_authenticated_request_succeeds(self, client, user, sample_jobs):
        """Authenticated HR user can export their own data."""
        response = client.post(
            "/api/exports",
            headers=user["headers"],
            json={
                "resource": "jobs",
                "filters": {},
                "columns": ["company", "position"],
                "format": "xlsx",
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class TestExportOwnership:
    """Test ownership filtering for exports."""
    
    def test_hr_cannot_export_other_hr_data(self, client, user, other_user):
        """HR user A cannot export HR user B's data."""
        # Create job for other HR user
        response = client.post(
            "/api/jobs",
            json={
                "company_name": "Other Company",
                "position": "Other Position",
                "description": "Other job",
            },
            headers=other_user["headers"],
        )
        assert response.status_code == 201
        
        # First HR user tries to export - should get empty result
        response = client.post(
            "/api/exports",
            headers=user["headers"],
            json={
                "resource": "jobs",
                "filters": {},
                "columns": ["company", "position"],
                "format": "xlsx",
            },
        )
        
        # Should return 400 with "No records match" message
        assert response.status_code == 400
        assert "No records match" in response.json()["detail"]
    
    def test_admin_can_export_all_data(self, client, user, other_user, admin):
        """Admin user can export data from all HR users."""
        # Create jobs for both HR users
        client.post(
            "/api/jobs",
            json={"company_name": "Company 1", "position": "Position 1", "description": "Desc 1"},
            headers=user["headers"],
        )
        client.post(
            "/api/jobs",
            json={"company_name": "Company 2", "position": "Position 2", "description": "Desc 2"},
            headers=other_user["headers"],
        )
        
        # Admin exports all jobs
        response = client.post(
            "/api/exports",
            headers=admin["headers"],
            json={
                "resource": "jobs",
                "filters": {},
                "columns": ["company", "position"],
                "format": "xlsx",
            },
        )
        
        assert response.status_code == 200
        
        # Parse XLSX and verify both jobs are present
        wb = load_workbook(io.BytesIO(response.content))
        ws = wb.active
        rows = list(ws.values)
        
        # Should have header + 2 data rows
        assert len(rows) == 3
        assert any("Company 1" in str(row) for row in rows)
        assert any("Company 2" in str(row) for row in rows)


class TestExportValidation:
    """Test request validation."""
    
    def test_unsupported_resource_returns_422(self, client, user):
        """Invalid resource type should return validation error."""
        response = client.post(
            "/api/exports",
            headers=user["headers"],
            json={
                "resource": "invalid_resource",
                "filters": {},
                "columns": ["name"],
                "format": "xlsx",
            },
        )
        assert response.status_code == 422
    
    def test_unsupported_format_returns_422(self, client, user):
        """Invalid format should return validation error."""
        response = client.post(
            "/api/exports",
            headers=user["headers"],
            json={
                "resource": "jobs",
                "filters": {},
                "columns": ["company"],
                "format": "invalid_format",
            },
        )
        assert response.status_code == 422
    
    def test_empty_columns_returns_422(self, client, user):
        """Empty columns list should return validation error."""
        response = client.post(
            "/api/exports",
            headers=user["headers"],
            json={
                "resource": "jobs",
                "filters": {},
                "columns": [],
                "format": "xlsx",
            },
        )
        assert response.status_code == 422
    
    def test_invalid_columns_returns_400(self, client, user, sample_jobs):
        """Invalid column names should return 400."""
        response = client.post(
            "/api/exports",
            headers=user["headers"],
            json={
                "resource": "jobs",
                "filters": {},
                "columns": ["invalid_column", "another_invalid"],
                "format": "xlsx",
            },
        )
        assert response.status_code == 400
        assert "No valid columns" in response.json()["detail"]


class TestJobExports:
    """Test job export functionality."""
    
    def test_export_all_jobs_xlsx(self, client, user, sample_jobs):
        """Export all jobs to XLSX."""
        response = client.post(
            "/api/exports",
            headers=user["headers"],
            json={
                "resource": "jobs",
                "filters": {},
                "columns": ["company", "position", "leads_count"],
                "format": "xlsx",
            },
        )
        
        assert response.status_code == 200
        assert "jobs_report" in response.headers["content-disposition"]
        
        # Parse XLSX
        wb = load_workbook(io.BytesIO(response.content))
        ws = wb.active
        rows = list(ws.values)
        
        # Verify header and data
        assert rows[0] == ("Company", "Position", "Applications")
        assert len(rows) == 3  # Header + 2 jobs
        assert any("Unicon Soft" in str(row) for row in rows)
        assert any("TechCorp" in str(row) for row in rows)
    
    def test_export_jobs_with_company_filter(self, client, user, sample_jobs):
        """Export jobs filtered by company."""
        response = client.post(
            "/api/exports",
            headers=user["headers"],
            json={
                "resource": "jobs",
                "filters": {"company": "Unicon Soft"},
                "columns": ["company", "position"],
                "format": "xlsx",
            },
        )
        
        assert response.status_code == 200
        
        wb = load_workbook(io.BytesIO(response.content))
        ws = wb.active
        rows = list(ws.values)
        
        # Should only have 1 job + header
        assert len(rows) == 2
        assert "Unicon Soft" in str(rows[1])
        assert "TechCorp" not in str(rows)
    
    def test_export_jobs_pdf(self, client, user, sample_jobs):
        """Export jobs to PDF."""
        response = client.post(
            "/api/exports",
            headers=user["headers"],
            json={
                "resource": "jobs",
                "filters": {},
                "columns": ["company", "position"],
                "format": "pdf",
            },
        )
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        
        # Verify PDF is valid
        pdf = PdfReader(io.BytesIO(response.content))
        assert len(pdf.pages) > 0
    
    def test_export_jobs_docx(self, client, user, sample_jobs):
        """Export jobs to DOCX."""
        response = client.post(
            "/api/exports",
            headers=user["headers"],
            json={
                "resource": "jobs",
                "filters": {},
                "columns": ["company", "position"],
                "format": "docx",
            },
        )
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        
        # Verify DOCX is valid
        doc = Document(io.BytesIO(response.content))
        assert len(doc.paragraphs) > 0


class TestApplicationExports:
    """Test application export functionality."""
    
    def test_export_all_applications(self, client, user, sample_applications):
        """Export all applications."""
        response = client.post(
            "/api/exports",
            headers=user["headers"],
            json={
                "resource": "applications",
                "filters": {},
                "columns": ["name", "email", "company", "position", "ai_score"],
                "format": "xlsx",
            },
        )
        
        assert response.status_code == 200
        
        wb = load_workbook(io.BytesIO(response.content))
        ws = wb.active
        rows = list(ws.values)
        
        # Should have all 3 applications
        assert len(rows) == 4  # Header + 3 apps
        assert any("John Doe" in str(row) for row in rows)
        assert any("Jane Smith" in str(row) for row in rows)
        assert any("Bob Johnson" in str(row) for row in rows)
    
    def test_export_applications_with_status_filter(self, client, user, sample_applications):
        """Export applications filtered by status."""
        response = client.post(
            "/api/exports",
            headers=user["headers"],
            json={
                "resource": "applications",
                "filters": {"application_status": "shortlisted"},
                "columns": ["name", "application_status"],
                "format": "xlsx",
            },
        )
        
        assert response.status_code == 200
        
        wb = load_workbook(io.BytesIO(response.content))
        ws = wb.active
        rows = list(ws.values)
        
        # Should only have John Doe (shortlisted)
        assert len(rows) == 2
        assert "John Doe" in str(rows[1])
    
    def test_export_applications_with_search(self, client, user, sample_applications):
        """Export applications with search filter."""
        response = client.post(
            "/api/exports",
            headers=user["headers"],
            json={
                "resource": "applications",
                "filters": {"search": "jane"},
                "columns": ["name", "email"],
                "format": "xlsx",
            },
        )
        
        assert response.status_code == 200
        
        wb = load_workbook(io.BytesIO(response.content))
        ws = wb.active
        rows = list(ws.values)
        
        # Should only have Jane Smith
        assert len(rows) == 2
        assert "Jane Smith" in str(rows[1])


class TestCandidateExports:
    """Test candidate export functionality."""
    
    def test_export_only_candidates(self, client, user, sample_applications):
        """Export should only include candidates (candidate_at IS NOT NULL)."""
        response = client.post(
            "/api/exports",
            headers=user["headers"],
            json={
                "resource": "candidates",
                "filters": {},
                "columns": ["name", "hiring_status"],
                "format": "xlsx",
            },
        )
        
        assert response.status_code == 200
        
        wb = load_workbook(io.BytesIO(response.content))
        ws = wb.active
        rows = list(ws.values)
        
        # Should only have Jane (she has candidate_at set)
        assert len(rows) == 2
        assert "Jane Smith" in str(rows[1])
        assert "John Doe" not in str(rows)
        assert "Bob Johnson" not in str(rows)


class TestInterviewExports:
    """Test interview export functionality."""
    
    def test_export_interviews(self, client, user, sample_interviews):
        """Export interviews."""
        response = client.post(
            "/api/exports",
            headers=user["headers"],
            json={
                "resource": "interviews",
                "filters": {},
                "columns": ["candidate_name", "interviewer", "status"],
                "format": "xlsx",
            },
        )
        
        assert response.status_code == 200
        
        wb = load_workbook(io.BytesIO(response.content))
        ws = wb.active
        rows = list(ws.values)
        
        assert len(rows) == 2  # Header + 1 interview
        assert "Jane Smith" in str(rows[1])
        assert "Tech Lead" in str(rows[1])


class TestEmptyResults:
    """Test handling of empty export results."""
    
    def test_export_with_no_matching_records_returns_400(self, client, user, sample_jobs):
        """Export with filters that match no records should return 400."""
        response = client.post(
            "/api/exports",
            headers=user["headers"],
            json={
                "resource": "jobs",
                "filters": {"company": "NonExistentCompany"},
                "columns": ["company", "position"],
                "format": "xlsx",
            },
        )
        
        assert response.status_code == 400
        assert "No records match" in response.json()["detail"]
    
    def test_export_no_jobs_returns_400(self, client, user):
        """Export when no jobs exist should return 400."""
        response = client.post(
            "/api/exports",
            headers=user["headers"],
            json={
                "resource": "jobs",
                "filters": {},
                "columns": ["company"],
                "format": "xlsx",
            },
        )
        
        assert response.status_code == 400
        assert "No records match" in response.json()["detail"]
