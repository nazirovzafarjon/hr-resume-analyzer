"""Universal Export Service for HR dashboard tables.

Handles filtering, querying, and generating exports in PDF, XLSX, and DOCX formats.
"""

from datetime import date, datetime, timedelta
from io import BytesIO
from typing import Any

from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.platypus.tables import GRID_STYLE
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import Session, contains_eager

from app.crud.query_utils import owner_filter, contains_pattern, escape_like
from app.models.application import Application, ApplicationStatus, AnalysisStatus, HiringStatus, InterviewStatus as AppInterviewStatus
from app.models.interview import Interview, InterviewStatus
from app.models.job import Job
from app.schemas.export import ExportFilters, ExportResource


# Column definitions for each resource
RESOURCE_COLUMNS = {
    "jobs": {
        "company": "Company",
        "position": "Position",
        "description": "Description",
        "required_skills": "Required Skills",
        "required_experience": "Required Experience",
        "leads_count": "Applications",
        "created_at": "Created At",
    },
    "applications": {
        "name": "Candidate",
        "email": "Email",
        "company": "Company",
        "position": "Position",
        "application_status": "Status",
        "analysis_status": "AI Status",
        "ai_score": "AI Score",
        "hiring_status": "Hiring Status",
        "interview_status": "Interview Status",
        "submitted_at": "Submitted At",
        "created_at": "Created At",
    },
    "candidates": {
        "name": "Candidate",
        "email": "Email",
        "company": "Company",
        "position": "Position",
        "hiring_status": "Hiring Status",
        "interview_status": "Interview Status",
        "ai_score": "AI Score",
        "candidate_at": "Candidate Since",
        "created_at": "Created At",
    },
    "interviews": {
        "candidate_name": "Candidate",
        "company": "Company",
        "position": "Position",
        "interviewer": "Interviewer",
        "scheduled_at": "Scheduled",
        "duration_minutes": "Duration (min)",
        "status": "Status",
        "meeting_link": "Meeting Link",
        "created_at": "Created At",
    },
}


class ExportService:
    """Service for generating filtered table exports."""
    
    def __init__(self, db: Session, owner_id: int | None):
        """Initialize export service.
        
        Args:
            db: Database session
            owner_id: HR user ID for ownership filtering (None = admin, all data)
        """
        self.db = db
        self.owner_id = owner_id
    
    def validate_columns(self, resource: ExportResource, columns: list[str]) -> list[str]:
        """Validate and filter requested columns against allowed columns.
        
        Args:
            resource: Resource type
            columns: Requested column keys
            
        Returns:
            List of valid column keys
            
        Raises:
            ValueError: If no valid columns remain
        """
        allowed = set(RESOURCE_COLUMNS[resource].keys())
        valid = [col for col in columns if col in allowed]
        
        if not valid:
            raise ValueError(
                f"No valid columns for resource '{resource}'. "
                f"Allowed: {', '.join(allowed)}"
            )
        
        return valid
    
    def _get_latest_job_id(self) -> int | None:
        """Get the latest job ID for the current owner.
        
        Returns:
            Job ID or None if no jobs exist
        """
        stmt = (
            select(Job.id)
            .where(owner_filter(Job.owner_id, self.owner_id))
            .order_by(Job.created_at.desc())
            .limit(1)
        )
        result = self.db.execute(stmt).scalar_one_or_none()
        return result
    
    def _apply_job_filter(self, stmt: Any, filters: ExportFilters, model: Any) -> Any:
        """Apply job-based filters to a query.
        
        Args:
            stmt: SQLAlchemy select statement
            filters: Export filters
            model: Model class (Application or Interview)
            
        Returns:
            Modified statement
        """
        # Determine job_id to filter by
        job_id = None
        if filters.use_latest_job:
            job_id = self._get_latest_job_id()
            if job_id is None:
                # No jobs exist, return empty result
                return stmt.where(False)
        elif filters.job_id:
            job_id = filters.job_id
        
        # Apply job filter if specified
        if job_id:
            if model == Application:
                stmt = stmt.where(Application.job_id == job_id)
            elif model == Interview:
                stmt = stmt.join(Application, Interview.candidate_id == Application.id)
                stmt = stmt.where(Application.job_id == job_id)
        
        # Apply company filter (via job)
        if filters.company:
            if model == Application:
                stmt = stmt.where(Job.company_name == filters.company)
            elif model == Interview:
                if job_id is None:  # Only join if not already joined
                    stmt = stmt.join(Application, Interview.candidate_id == Application.id)
                stmt = stmt.join(Job, Application.job_id == Job.id)
                stmt = stmt.where(Job.company_name == filters.company)
        
        return stmt
    
    def _apply_date_filter(self, stmt: Any, filters: ExportFilters, date_column: Any) -> Any:
        """Apply date range filter to a query.
        
        Args:
            stmt: SQLAlchemy select statement
            filters: Export filters
            date_column: Column to filter on (e.g., Job.created_at)
            
        Returns:
            Modified statement
        """
        if filters.date_from:
            stmt = stmt.where(date_column >= filters.date_from)
        if filters.date_to:
            # Include the entire day
            stmt = stmt.where(date_column < filters.date_to + timedelta(days=1))
        return stmt
    
    def query_jobs(self, filters: ExportFilters) -> list[dict[str, Any]]:
        """Query and format jobs data.
        
        Args:
            filters: Export filters
            
        Returns:
            List of job records as dicts
        """
        stmt = (
            select(Job)
            .where(owner_filter(Job.owner_id, self.owner_id))
            .order_by(Job.created_at.desc())
        )
        
        # Apply company filter
        if filters.company:
            stmt = stmt.where(Job.company_name == filters.company)
        
        # Apply date filter
        stmt = self._apply_date_filter(stmt, filters, Job.created_at)
        
        results = self.db.execute(stmt).scalars().all()
        
        return [
            {
                "company": job.company_name,
                "position": job.position,
                "description": job.description,
                "required_skills": job.required_skills,
                "required_experience": job.required_experience,
                "leads_count": job.leads_count,
                "created_at": job.created_at,
            }
            for job in results
        ]
    
    def query_applications(
        self, 
        filters: ExportFilters, 
        candidates_only: bool = False
    ) -> list[dict[str, Any]]:
        """Query and format applications/candidates data.
        
        Args:
            filters: Export filters
            candidates_only: If True, filter to only candidates (candidate_at IS NOT NULL)
            
        Returns:
            List of application records as dicts
        """
        stmt = (
            select(Application)
            .join(Application.job)
            .options(contains_eager(Application.job))
            .where(owner_filter(Job.owner_id, self.owner_id))
        )
        
        # Candidates-only filter
        if candidates_only:
            stmt = stmt.where(Application.candidate_at.isnot(None))
        
        # Apply job and company filters
        stmt = self._apply_job_filter(stmt, filters, Application)
        
        # Apply status filters
        if filters.application_status:
            try:
                status = ApplicationStatus(filters.application_status)
                stmt = stmt.where(Application.application_status == status)
            except ValueError:
                pass
        
        if filters.analysis_status:
            try:
                status = AnalysisStatus(filters.analysis_status)
                stmt = stmt.where(Application.analysis_status == status)
            except ValueError:
                pass
        
        if filters.hiring_status:
            try:
                status = HiringStatus(filters.hiring_status)
                stmt = stmt.where(Application.hiring_status == status)
            except ValueError:
                pass
        
        if filters.interview_status:
            try:
                status = AppInterviewStatus(filters.interview_status)
                stmt = stmt.where(Application.interview_status == status)
            except ValueError:
                pass
        
        # Apply search filter (name or email)
        if filters.search:
            search_pattern = contains_pattern(escape_like(filters.search))
            stmt = stmt.where(
                or_(
                    Application.name.ilike(search_pattern),
                    Application.email.ilike(search_pattern),
                )
            )
        
        # Apply date filter
        stmt = self._apply_date_filter(stmt, filters, Application.submitted_at)
        
        # Order by submission date
        stmt = stmt.order_by(Application.submitted_at.desc())
        
        results = self.db.execute(stmt).scalars().all()
        
        return [
            {
                "name": app.name,
                "email": app.email,
                "company": app.company_name,
                "position": app.position,
                "application_status": app.application_status.value,
                "analysis_status": app.analysis_status.value,
                "ai_score": app.ai_score,
                "hiring_status": app.hiring_status.value,
                "interview_status": app.interview_status.value,
                "submitted_at": app.submitted_at,
                "candidate_at": app.candidate_at,
                "created_at": app.created_at,
            }
            for app in results
        ]
    
    def query_interviews(self, filters: ExportFilters) -> list[dict[str, Any]]:
        """Query and format interviews data.
        
        Args:
            filters: Export filters
            
        Returns:
            List of interview records as dicts
        """
        stmt = (
            select(Interview)
            .join(Interview.candidate)
            .join(Application.job)
            .options(
                contains_eager(Interview.candidate).contains_eager(Application.job)
            )
            .where(owner_filter(Job.owner_id, self.owner_id))
        )
        
        # Apply job and company filters
        stmt = self._apply_job_filter(stmt, filters, Interview)
        
        # Apply interview status filter
        if filters.interview_status:
            try:
                status = InterviewStatus(filters.interview_status)
                stmt = stmt.where(Interview.status == status)
            except ValueError:
                pass
        
        # Apply search filter (candidate name or interviewer)
        if filters.search:
            search_pattern = contains_pattern(escape_like(filters.search))
            stmt = stmt.where(
                or_(
                    Application.name.ilike(search_pattern),
                    Interview.interviewer.ilike(search_pattern),
                )
            )
        
        # Apply date filter on scheduled_at
        stmt = self._apply_date_filter(stmt, filters, Interview.scheduled_at)
        
        # Order by scheduled date
        stmt = stmt.order_by(Interview.scheduled_at.desc())
        
        results = self.db.execute(stmt).scalars().all()
        
        return [
            {
                "candidate_name": interview.candidate.name,
                "company": interview.candidate.company_name,
                "position": interview.candidate.position,
                "interviewer": interview.interviewer,
                "scheduled_at": interview.scheduled_at,
                "duration_minutes": interview.duration_minutes,
                "status": interview.status.value,
                "meeting_link": interview.meeting_link or "",
                "created_at": interview.created_at,
            }
            for interview in results
        ]
    
    def get_data(
        self, 
        resource: ExportResource, 
        filters: ExportFilters
    ) -> list[dict[str, Any]]:
        """Get filtered data for a resource.
        
        Args:
            resource: Resource type to query
            filters: Filters to apply
            
        Returns:
            List of records as dicts
        """
        if resource == "jobs":
            return self.query_jobs(filters)
        elif resource == "applications":
            return self.query_applications(filters, candidates_only=False)
        elif resource == "candidates":
            return self.query_applications(filters, candidates_only=True)
        elif resource == "interviews":
            return self.query_interviews(filters)
        else:
            raise ValueError(f"Unsupported resource: {resource}")
    
    def format_value(self, value: Any) -> str:
        """Format a value for display in exports.
        
        Args:
            value: Raw value
            
        Returns:
            Formatted string
        """
        if value is None:
            return ""
        elif isinstance(value, datetime):
            return value.strftime("%d %b %Y, %H:%M")
        elif isinstance(value, date):
            return value.strftime("%d %b %Y")
        elif isinstance(value, float):
            return f"{value:.1f}"
        elif isinstance(value, bool):
            return "Yes" if value else "No"
        else:
            return str(value)
    
    def generate_xlsx(
        self,
        resource: ExportResource,
        data: list[dict[str, Any]],
        columns: list[str],
    ) -> BytesIO:
        """Generate XLSX export.
        
        Args:
            resource: Resource type
            data: Filtered data records
            columns: Columns to include
            
        Returns:
            BytesIO containing the XLSX file
        """
        wb = Workbook()
        ws = wb.active
        ws.title = resource.capitalize()
        
        # Get column headers
        column_map = RESOURCE_COLUMNS[resource]
        headers = [column_map[col] for col in columns]
        
        # Write header row
        ws.append(headers)
        
        # Style header row
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF")
        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")
        
        # Write data rows
        for record in data:
            row = [self.format_value(record.get(col)) for col in columns]
            ws.append(row)
        
        # Auto-size columns
        for idx, col in enumerate(columns, start=1):
            column_letter = get_column_letter(idx)
            max_length = len(column_map[col])
            
            for cell in ws[column_letter]:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column_letter].width = adjusted_width
        
        # Freeze header row
        ws.freeze_panes = "A2"
        
        # Enable autofilter
        ws.auto_filter.ref = ws.dimensions
        
        # Save to BytesIO
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        return output
    
    def generate_pdf(
        self,
        resource: ExportResource,
        data: list[dict[str, Any]],
        columns: list[str],
        filters: ExportFilters,
    ) -> BytesIO:
        """Generate PDF export.
        
        Args:
            resource: Resource type
            data: Filtered data records
            columns: Columns to include
            filters: Applied filters (for metadata)
            
        Returns:
            BytesIO containing the PDF file
        """
        output = BytesIO()
        doc = SimpleDocTemplate(
            output,
            pagesize=letter,
            rightMargin=0.5*inch,
            leftMargin=0.5*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch,
        )
        
        elements = []
        styles = getSampleStyleSheet()
        
        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor("#1a365d"),
            spaceAfter=12,
            alignment=WD_ALIGN_PARAGRAPH.LEFT,
        )
        title = Paragraph(f"{resource.capitalize()} Report", title_style)
        elements.append(title)
        
        # Metadata
        meta_style = ParagraphStyle(
            'Meta',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor("#4a5568"),
            spaceAfter=6,
        )
        
        now = datetime.now()
        elements.append(Paragraph(f"<b>Generated:</b> {now.strftime('%d %b %Y, %H:%M')}", meta_style))
        
        # Applied filters
        filter_items = []
        if filters.company:
            filter_items.append(f"Company: {filters.company}")
        if filters.use_latest_job:
            filter_items.append("Job: Latest")
        elif filters.job_id:
            filter_items.append(f"Job ID: {filters.job_id}")
        if filters.application_status:
            filter_items.append(f"Application Status: {filters.application_status}")
        if filters.analysis_status:
            filter_items.append(f"Analysis Status: {filters.analysis_status}")
        if filters.hiring_status:
            filter_items.append(f"Hiring Status: {filters.hiring_status}")
        if filters.interview_status:
            filter_items.append(f"Interview Status: {filters.interview_status}")
        if filters.date_from:
            filter_items.append(f"From: {filters.date_from.strftime('%d %b %Y')}")
        if filters.date_to:
            filter_items.append(f"To: {filters.date_to.strftime('%d %b %Y')}")
        if filters.search:
            filter_items.append(f"Search: {filters.search}")
        
        if filter_items:
            elements.append(Paragraph(f"<b>Filters:</b> {', '.join(filter_items)}", meta_style))
        
        elements.append(Paragraph(f"<b>Records:</b> {len(data)}", meta_style))
        elements.append(Spacer(1, 0.25*inch))
        
        # Table
        if not data:
            elements.append(Paragraph("No records match the selected filters.", styles['Normal']))
        else:
            column_map = RESOURCE_COLUMNS[resource]
            headers = [column_map[col] for col in columns]
            
            table_data = [headers]
            for record in data:
                row = [self.format_value(record.get(col)) for col in columns]
                # Truncate long text to prevent layout issues
                row = [str(val)[:100] + "..." if len(str(val)) > 100 else str(val) for val in row]
                table_data.append(row)
            
            # Calculate column widths
            available_width = 7.5 * inch
            col_count = len(columns)
            col_width = available_width / col_count
            
            table = Table(table_data, colWidths=[col_width] * col_count, repeatRows=1)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#366092")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('TOPPADDING', (0, 1), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            elements.append(table)
        
        doc.build(elements)
        output.seek(0)
        return output
    
    def generate_docx(
        self,
        resource: ExportResource,
        data: list[dict[str, Any]],
        columns: list[str],
        filters: ExportFilters,
    ) -> BytesIO:
        """Generate DOCX export.
        
        Args:
            resource: Resource type
            data: Filtered data records
            columns: Columns to include
            filters: Applied filters (for metadata)
            
        Returns:
            BytesIO containing the DOCX file
        """
        doc = Document()
        
        # Title
        title = doc.add_heading(f"{resource.capitalize()} Report", level=1)
        title.alignment = WD_ALIGN_PARAGRAPH.LEFT
        
        # Metadata
        now = datetime.now()
        metadata = doc.add_paragraph()
        metadata.add_run("Generated: ").bold = True
        metadata.add_run(f"{now.strftime('%d %b %Y, %H:%M')}\n")
        
        # Applied filters
        filter_items = []
        if filters.company:
            filter_items.append(f"Company: {filters.company}")
        if filters.use_latest_job:
            filter_items.append("Job: Latest")
        elif filters.job_id:
            filter_items.append(f"Job ID: {filters.job_id}")
        if filters.application_status:
            filter_items.append(f"Application Status: {filters.application_status}")
        if filters.analysis_status:
            filter_items.append(f"Analysis Status: {filters.analysis_status}")
        if filters.hiring_status:
            filter_items.append(f"Hiring Status: {filters.hiring_status}")
        if filters.interview_status:
            filter_items.append(f"Interview Status: {filters.interview_status}")
        if filters.date_from:
            filter_items.append(f"From: {filters.date_from.strftime('%d %b %Y')}")
        if filters.date_to:
            filter_items.append(f"To: {filters.date_to.strftime('%d %b %Y')}")
        if filters.search:
            filter_items.append(f"Search: {filters.search}")
        
        if filter_items:
            filters_para = metadata.add_run("Filters: ")
            filters_para.bold = True
            metadata.add_run(", ".join(filter_items) + "\n")
        
        records_run = metadata.add_run("Records: ")
        records_run.bold = True
        metadata.add_run(str(len(data)))
        
        doc.add_paragraph()  # Spacer
        
        # Table
        if not data:
            doc.add_paragraph("No records match the selected filters.")
        else:
            column_map = RESOURCE_COLUMNS[resource]
            headers = [column_map[col] for col in columns]
            
            table = doc.add_table(rows=1, cols=len(columns))
            table.style = 'Light Grid Accent 1'
            
            # Header row
            header_cells = table.rows[0].cells
            for idx, header in enumerate(headers):
                header_cells[idx].text = header
                # Bold header
                for paragraph in header_cells[idx].paragraphs:
                    for run in paragraph.runs:
                        run.font.bold = True
            
            # Data rows
            for record in data:
                row_cells = table.add_row().cells
                for idx, col in enumerate(columns):
                    value = self.format_value(record.get(col))
                    # Truncate long text
                    if len(value) > 200:
                        value = value[:200] + "..."
                    row_cells[idx].text = value
        
        output = BytesIO()
        doc.save(output)
        output.seek(0)
        return output
    
    def export(
        self,
        resource: ExportResource,
        filters: ExportFilters,
        columns: list[str],
        format: str,
    ) -> tuple[BytesIO, str, int]:
        """Generate export file.
        
        Args:
            resource: Resource type
            filters: Filters to apply
            columns: Columns to include
            format: Output format (pdf, xlsx, docx)
            
        Returns:
            Tuple of (file_bytes, filename, record_count)
            
        Raises:
            ValueError: If no records match filters or invalid parameters
        """
        # Validate columns
        valid_columns = self.validate_columns(resource, columns)
        
        # Get filtered data
        data = self.get_data(resource, filters)
        
        if not data:
            raise ValueError("No records match the selected filters")
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y-%m-%d")
        filename = f"{resource}_report_{timestamp}.{format}"
        
        # Generate file based on format
        if format == "xlsx":
            file_bytes = self.generate_xlsx(resource, data, valid_columns)
        elif format == "pdf":
            file_bytes = self.generate_pdf(resource, data, valid_columns, filters)
        elif format == "docx":
            file_bytes = self.generate_docx(resource, data, valid_columns, filters)
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        return file_bytes, filename, len(data)
