"""Pydantic schemas for dynamic AI analysis translation.

These schemas model presentation-layer translations of candidate/application
analysis results. The database is never mutated by these operations.
"""

from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class TranslateAnalysisRequest(BaseModel):
    """Request payload for POST /api/translations/translate-analysis."""

    target_language: str = Field(
        description="Target language code (e.g. 'uz', 'kiril', 'ru', 'en')."
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured analysis details to translate (summary, strengths, weaknesses, etc.).",
    )

    model_config = ConfigDict(extra="ignore")


class TranslateAnalysisResponse(BaseModel):
    """Response returned by POST /api/translations/translate-analysis."""

    target_language: str
    translated_payload: dict[str, Any]
    cached: bool = False

    model_config = ConfigDict(extra="ignore")
