from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from app.domain.enums import ClassificationGrade, WorkCategory


class TenderRequirements(BaseModel):
    """Structured tender requirements. Later produced by the extraction layer."""

    reference: str
    title: str | None = None
    work_category: WorkCategory | None = None
    required_classification_grade: ClassificationGrade | None = None
    min_registered_capital: Decimal | None = Field(default=None, ge=0)
    min_similar_projects: int | None = Field(default=None, ge=0)
    min_similar_project_value: Decimal | None = Field(default=None, ge=0)
    experience_lookback_years: int = Field(default=5, ge=1)
    min_years_experience: int | None = Field(default=None, ge=0)
    submission_deadline: date | None = None
    bid_guarantee_amount: Decimal | None = Field(default=None, ge=0)
    unverified_fields: list[str] = Field(
        default_factory=list,
        description="Requirements the document states but the extractor could not verify.",
    )
