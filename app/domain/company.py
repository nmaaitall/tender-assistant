from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from app.domain.enums import ClassificationGrade, WorkCategory


class Classification(BaseModel):
    category: WorkCategory
    grade: ClassificationGrade


class PastProject(BaseModel):
    title: str
    category: WorkCategory
    value: Decimal = Field(ge=0)
    completed_on: date
    client: str | None = None


class CompanyProfile(BaseModel):
    """Company data entered once by the user. Optional fields mean 'not stated yet'."""

    name: str
    classifications: list[Classification] = Field(default_factory=list)
    registered_capital: Decimal | None = Field(default=None, ge=0)
    employee_count: int | None = Field(default=None, ge=0)
    past_projects: list[PastProject] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    max_bid_guarantee: Decimal | None = Field(default=None, ge=0)

    def best_grade_for(self, category: WorkCategory) -> ClassificationGrade | None:
        grades = [c.grade for c in self.classifications if c.category == category]
        return min(grades, key=lambda grade: grade.value) if grades else None
