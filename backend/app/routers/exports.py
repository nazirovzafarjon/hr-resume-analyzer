"""API endpoints for exporting HR dashboard table data.

Allows authenticated HR users to export filtered data in PDF, XLSX, or DOCX formats.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import AccessScope, get_access_scope
from app.schemas.export import ExportRequest, ExportResponse
from app.services.export_service import ExportService


router = APIRouter(prefix="/exports", tags=["exports"])


# Content type mapping for different formats
CONTENT_TYPES = {
    "pdf": "application/pdf",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@router.post("", response_class=StreamingResponse)
def export_table(
    request: ExportRequest,
    db: Session = Depends(get_db),
    scope: AccessScope = Depends(get_access_scope),
):
    """Export filtered table data to PDF, XLSX, or DOCX.
    
    The export respects ownership:
    - HR users can only export their own data
    - Admin users (owner_id=None) can export all data
    
    Args:
        request: Export configuration (resource, filters, columns, format)
        db: Database session
        scope: Access scope (determines ownership filtering)
        
    Returns:
        StreamingResponse with the generated file
        
    Raises:
        HTTPException: If no records match filters or invalid parameters
    """
    service = ExportService(db, scope.owner_id)
    
    try:
        file_bytes, filename, record_count = service.export(
            resource=request.resource,
            filters=request.filters,
            columns=request.columns,
            format=request.format,
        )
        
        content_type = CONTENT_TYPES[request.format]
        
        return StreamingResponse(
            file_bytes,
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Log the error in production
        raise HTTPException(
            status_code=500,
            detail="An error occurred while generating the export. Please try again.",
        )
