"""Shared pydantic schemas for the self-improvement engine (PLN-001 A line)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ExperienceEntry(BaseModel):
    """A pattern-level experience entry produced by the reflection generator.

    Entries only hold de-identified pattern descriptions (situation / action /
    lesson); raw ticket PII must never be stored here.
    """

    situation: str = Field(description="Pattern description of the failing situation.")
    action: str = Field(description="The behaviour to apply when the situation recurs.")
    lesson: str = Field(description="The distilled lesson/root cause.")
    source: str = Field(
        default="reflection",
        description="Origin of the entry: reflection (LLM) or fallback (template).",
    )
    target_error_type: str = Field(
        default="",
        description="Error type this entry aims to fix, e.g. route_error.",
    )


class ReflectionResult(BaseModel):
    """Result of reflecting over one failure sample."""

    sample_id: str
    entry: ExperienceEntry | None = Field(default=None, description="Entry when reflection succeeded.")
    error: str | None = Field(default=None, description="Failure reason when reflection failed.")
