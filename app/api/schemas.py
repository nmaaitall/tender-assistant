from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from app.domain.company import CompanyProfile
from app.domain.tender import TenderRequirements

EXAMPLE_REQUEST = {
    "profile": {
        "name": "Al Rawabi Contracting",
        "classifications": [{"category": "buildings", "grade": 3}],
        "registered_capital": "150000",
        "employee_count": 24,
        "past_projects": [
            {
                "title": "Zarqa school extension",
                "category": "buildings",
                "value": "320000",
                "completed_on": "2023-05-10",
            },
            {
                "title": "Municipal offices refurbishment",
                "category": "buildings",
                "value": "410000",
                "completed_on": "2024-11-01",
            },
        ],
        "certifications": ["ISO 9001"],
        "max_bid_guarantee": "25000",
    },
    "tender": {
        "reference": "ZM-2026-014",
        "title": "Construction of a municipal service building",
        "work_category": "buildings",
        "required_classification_grade": 3,
        "min_registered_capital": "100000",
        "min_similar_projects": 2,
        "min_similar_project_value": "250000",
        "experience_lookback_years": 5,
        "min_years_experience": 3,
        "submission_deadline": "2026-10-15",
        "bid_guarantee_amount": "20000",
    },
}


class EvaluationRequest(BaseModel):
    """A company profile and the requirements extracted from one tender document."""

    profile: CompanyProfile
    tender: TenderRequirements
    as_of: date | None = Field(
        default=None,
        description="Evaluation date. Defaults to today. Set it to make results reproducible.",
    )

    model_config = {"json_schema_extra": {"examples": [EXAMPLE_REQUEST]}}


class HealthResponse(BaseModel):
    status: str
    version: str
