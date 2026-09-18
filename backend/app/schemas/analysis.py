"""Pydantic schemas for resume analysis results."""

from pydantic import BaseModel


class SkillMatch(BaseModel):
    """A single required skill and whether it appears in the resume."""
    skill: str
    found: bool


class AnalysisResult(BaseModel):
    """Result of comparing a resume against a job's requirements.

    ``score`` is a percentage (0-100) reflecting how many required skills
    were matched.
    """
    score: float
    matched_skills: list[str]
    missing_skills: list[str]
    skill_matches: list[SkillMatch]
    summary: str