"""Router for dynamic on-the-fly translations.

Endpoints here translate presentation data without modifying database records.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.translation import (
    TranslateAnalysisRequest,
    TranslateAnalysisResponse,
)
from app.services.ai.job_analyzer import AIServiceError
from app.services.ai.translation_service import translate_analysis_payload

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/translate-analysis",
    response_model=TranslateAnalysisResponse,
    summary="Translate dynamic AI analysis details on-the-fly",
)
async def translate_analysis(
    req: TranslateAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TranslateAnalysisResponse:
    """Translate an application analysis payload on-the-fly.

    - Authenticated HR / Recruiter / Admin access only.
    - Presentation-layer only: does NOT modify or overwrite PostgreSQL records.
    - Caches translations to prevent duplicate provider requests and rate limits.
    """
    try:
        translated_payload, is_cached = await translate_analysis_payload(
            payload=req.payload,
            target_language=req.target_language,
            current_user_id=current_user.id,
            db=db,
        )
    except AIServiceError as exc:
        logger.warning(
            "Translation request failed for user_id=%s target=%s: %s",
            current_user.id,
            req.target_language,
            exc.message,
        )
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.message,
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error during analysis translation: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to translate analysis content.",
        ) from exc

    return TranslateAnalysisResponse(
        target_language=req.target_language,
        translated_payload=translated_payload,
        cached=is_cached,
    )
