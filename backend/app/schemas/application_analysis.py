"""Pydantic schemas for AI application analysis.

The AI provider's answer is untrusted input: everything below is normalised and
validated before it is stored in ``workers.ai_analysis_details``.

Two rules are encoded here explicitly:

* ``match_percentage`` is always a 0–100 number. Model output such as ``150``,
  ``"87%"`` or ``"high"`` is normalised (or rejected) instead of being stored
  as-is, so the UI can never display a nonsense match.
* ``ai_recommendation`` is the **advisory** AI suggestion. It is deliberately a
  separate field (and a separate type) from the HR-owned
  ``hiring_status``/``application_status``: the AI can suggest, HR decides.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.worker import AnalysisStatus

#: Advisory AI recommendation values (mirror the hiring categories, but are not
#: the HR decision).
AIRecommendationType = Literal["strong_hire", "hire", "weak_hire", "do_not_hire"]

#: Guard rails so a runaway model cannot store an unbounded payload.
MAX_LIST_ITEMS = 25
MAX_ITEM_LENGTH = 400
MAX_SUMMARY_LENGTH = 4000

#: Tolerated spellings of the recommendation values.
_RECOMMENDATION_ALIASES: dict[str, str] = {
    "strong hire": "strong_hire",
    "stronghire": "strong_hire",
    "weak hire": "weak_hire",
    "weakhire": "weak_hire",
    "do not hire": "do_not_hire",
    "donothire": "do_not_hire",
    "no hire": "do_not_hire",
}


def _clean_text(value: Any, limit: int = MAX_SUMMARY_LENGTH) -> str:
    """Return a trimmed string (non-strings are stringified, ``None`` → "")."""
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    return " ".join(value.split())[:limit]


def _clean_list(value: Any) -> list[str]:
    """Normalise any model output into a clean, bounded list of strings."""
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if isinstance(value, dict):
        value = list(value.values())
    if not isinstance(value, list):
        return []

    cleaned: list[str] = []
    for item in value:
        if isinstance(item, dict):
            # Models sometimes answer with objects ({"skill": "Python"}).
            parts = [str(v) for v in item.values() if isinstance(v, (str, int, float))]
            item = " — ".join(parts)
        text = _clean_text(item, MAX_ITEM_LENGTH)
        if text and text not in cleaned:
            cleaned.append(text)
        if len(cleaned) >= MAX_LIST_ITEMS:
            break
    return cleaned


def _normalise_percentage(value: Any) -> Any:
    """Coerce model output into a 0–100 number, clamping out-of-range values.

    ``150`` → ``100``, ``-5`` → ``0``, ``"87%"`` → ``87.0``, ``87.456`` →
    ``87.46``. Non-numeric output raises a validation error so the analysis is
    marked as failed instead of storing a fabricated score.
    """
    if isinstance(value, bool):
        raise ValueError("match_percentage must be a number")
    if isinstance(value, str):
        text = value.strip().replace("%", "").replace(",", ".")
        if not text:
            raise ValueError("match_percentage is empty")
        try:
            value = float(text)
        except ValueError as exc:
            raise ValueError("match_percentage must be a number") from exc
    if not isinstance(value, (int, float)):
        raise ValueError("match_percentage must be a number")

    number = float(value)
    if number < 0:
        return 0.0
    if number > 100:
        return 100.0
    return round(number, 2)


def _normalise_recommendation(value: Any) -> Any:
    """Map the model's wording onto an advisory recommendation value."""
    if not isinstance(value, str):
        return None
    key = " ".join(value.strip().lower().replace("-", " ").split())
    if key in _RECOMMENDATION_ALIASES:
        return _RECOMMENDATION_ALIASES[key]
    normalised = key.replace(" ", "_")
    if normalised in {"strong_hire", "hire", "weak_hire", "do_not_hire"}:
        return normalised
    # Unusable wording (e.g. "maybe"): report "not provided" instead of
    # inventing a recommendation for HR.
    return None


class ApplicationAnalysis(BaseModel):
    """Structured comparison of a job's requirements against one application.

    Produced by the AI provider from the job requirements, the submitted
    application-form answers and the resume text, then validated here before
    being persisted. It is *advisory* information for HR only.
    """

    match_percentage: float = Field(ge=0, le=100)
    summary: str = ""

    matched_requirements: list[str] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)

    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)

    experience_analysis: str = ""
    education_analysis: str = ""

    relevant_experience: list[str] = Field(default_factory=list)
    relevant_projects: list[str] = Field(default_factory=list)

    # Advisory only — never the HR decision.
    ai_recommendation: AIRecommendationType | None = None

    # Context recorded when the analysis was persisted (filled in by the
    # application-analysis service, not by the model).
    resume_text_available: bool = False
    analyzed_at: datetime | None = None
    model: str = ""

    model_config = ConfigDict(extra="ignore")

    _validate_percentage = field_validator("match_percentage", mode="before")(
        _normalise_percentage
    )
    _validate_recommendation = field_validator(
        "ai_recommendation", mode="before"
    )(_normalise_recommendation)
    _validate_summary = field_validator("summary", mode="before")(
        lambda value: _clean_text(value, MAX_SUMMARY_LENGTH)
    )
    _validate_experience = field_validator("experience_analysis", mode="before")(
        lambda value: _clean_text(value)
    )
    _validate_education = field_validator("education_analysis", mode="before")(
        lambda value: _clean_text(value)
    )
    _validate_lists = field_validator(
        "matched_requirements",
        "missing_requirements",
        "matched_skills",
        "missing_skills",
        "strengths",
        "weaknesses",
        "risks",
        "relevant_experience",
        "relevant_projects",
        mode="before",
    )(_clean_list)


class ApplicationAnalysisResponse(BaseModel):
    """Stored analysis state of an application.

    Returned by ``GET /api/workers/{id}/analysis``: it reads PostgreSQL only and
    never triggers a new AI request.
    """

    worker_id: int
    analysis_status: AnalysisStatus
    analysis_error: str | None = None
    analysis_started_at: datetime | None = None
    ai_score: float
    analysis: ApplicationAnalysis | None = None

    model_config = ConfigDict(from_attributes=True)
