"""Schemas for the Universal Export system.

Allows HR users to export filtered table data to PDF, XLSX, or DOCX formats.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator


ExportResource = Literal["jobs", "applications", "candidates", "interviews"]
ExportFormat = Literal["pdf", "xlsx", "docx"]


class ExportFilters(BaseModel):
    """Generic filters applicable across resources."""
    
    # Company filter (applies to all resources via job relationship)
    company: str | None = None
    
    # Job filter - can be "latest" or a specific job_id
    job_id: int | None = None
    use_latest_job: bool = False
    
    # Status filters (resource-specific, ignored if not applicable)
    application_status: str | None = None
    analysis_status: str | None = None
    hiring_status: str | None = None
    interview_status: str | None = None
    
    # Date range filters
    date_from: date | None = None
    date_to: date | None = None
    
    # Search query (name/email for applications, candidate name for interviews)
    search: str | None = None


class ExportRequest(BaseModel):
    """Request to export table data."""
    
    resource: ExportResource = Field(..., description="Type of data to export")
    filters: ExportFilters = Field(default_factory=ExportFilters, description="Filters to apply")
    columns: list[str] = Field(..., min_length=1, description="Columns to include in export")
    format: ExportFormat = Field(..., description="Output file format")
    
    @field_validator("columns")
    @classmethod
    def validate_non_empty_columns(cls, v: list[str]) -> list[str]:
        """Ensure at least one column is selected."""
        if not v:
            raise ValueError("At least one column must be selected")
        return v


class ExportResponse(BaseModel):
    """Response indicating export file details."""
    
    filename: str
    format: ExportFormat
    record_count: int
    message: str | None = None
