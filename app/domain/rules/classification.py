from __future__ import annotations

from datetime import date

from app.domain.company import CompanyProfile
from app.domain.results import RuleResult
from app.domain.rules.base import QualificationRule
from app.domain.tender import TenderRequirements


class ClassificationRule(QualificationRule):
    rule_id = "classification"
    fields = ("work_category", "required_classification_grade")

    def evaluate(
        self,
        profile: CompanyProfile,
        tender: TenderRequirements,
        as_of: date,
    ) -> RuleResult:
        required_grade = tender.required_classification_grade
        if required_grade is None:
            return self.not_applicable("Tender states no classification requirement.")

        category = tender.work_category
        if category is None:
            return self.unknown("Tender work category could not be identified.")

        required = f"grade {required_grade.value} or higher in {category.value}"
        if not profile.classifications:
            return self.unknown("Company classifications are missing from the profile.", required)

        held_grade = profile.best_grade_for(category)
        if held_grade is None:
            return self.failed(
                f"Company holds no classification in {category.value}.",
                required,
                "no classification in this category",
                remediable=False,
            )

        actual = f"grade {held_grade.value} in {category.value}"
        if held_grade.meets(required_grade):
            return self.passed("Classification requirement met.", required, actual)

        return self.failed(
            f"Tender requires classification grade {required_grade.value} in {category.value}; "
            f"company holds grade {held_grade.value}.",
            required,
            actual,
            remediable=False,
        )
