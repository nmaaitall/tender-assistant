from datetime import date
from decimal import Decimal

import pytest

from app.domain.company import Classification, CompanyProfile, PastProject
from app.domain.enums import ClassificationGrade, WorkCategory
from app.domain.tender import TenderRequirements

TODAY = date(2026, 9, 2)


@pytest.fixture
def today() -> date:
    return TODAY


@pytest.fixture
def profile() -> CompanyProfile:
    return CompanyProfile(
        name="Al Rawabi Contracting",
        classifications=[
            Classification(category=WorkCategory.BUILDINGS, grade=ClassificationGrade.GRADE_3)
        ],
        registered_capital=Decimal("150000"),
        employee_count=24,
        past_projects=[
            PastProject(
                title="Zarqa school extension",
                category=WorkCategory.BUILDINGS,
                value=Decimal("320000"),
                completed_on=date(2023, 5, 10),
            ),
            PastProject(
                title="Municipal offices refurbishment",
                category=WorkCategory.BUILDINGS,
                value=Decimal("410000"),
                completed_on=date(2024, 11, 1),
            ),
            PastProject(
                title="Warehouse construction",
                category=WorkCategory.BUILDINGS,
                value=Decimal("180000"),
                completed_on=date(2018, 3, 20),
            ),
        ],
        certifications=["ISO 9001"],
        max_bid_guarantee=Decimal("25000"),
    )


@pytest.fixture
def tender() -> TenderRequirements:
    return TenderRequirements(
        reference="ZM-2026-014",
        title="Construction of a municipal service building",
        work_category=WorkCategory.BUILDINGS,
        required_classification_grade=ClassificationGrade.GRADE_3,
        min_registered_capital=Decimal("100000"),
        min_similar_projects=2,
        min_similar_project_value=Decimal("250000"),
        experience_lookback_years=5,
        min_years_experience=5,
        submission_deadline=date(2026, 10, 15),
        bid_guarantee_amount=Decimal("20000"),
    )
