from __future__ import annotations

from datetime import date

from app.domain.company import CompanyProfile
from app.domain.results import RuleResult
from app.domain.rules.base import QualificationRule, format_money
from app.domain.tender import TenderRequirements


class CapitalRule(QualificationRule):
    rule_id = "registered_capital"

    def evaluate(
        self,
        profile: CompanyProfile,
        tender: TenderRequirements,
        as_of: date,
    ) -> RuleResult:
        minimum = tender.min_registered_capital
        if minimum is None:
            return self.not_applicable("Tender states no registered capital requirement.")

        required = f"at least {format_money(minimum)}"
        if profile.registered_capital is None:
            return self.unknown("Registered capital is missing from the profile.", required)

        actual = format_money(profile.registered_capital)
        if profile.registered_capital >= minimum:
            return self.passed("Registered capital requirement met.", required, actual)

        return self.failed(
            f"Tender requires registered capital of {format_money(minimum)}; "
            f"company profile shows {actual}.",
            required,
            actual,
            remediable=True,
        )
