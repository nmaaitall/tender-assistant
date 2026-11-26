from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal

from app.domain.company import CompanyProfile
from app.domain.enums import RuleStatus
from app.domain.results import RuleResult
from app.domain.tender import TenderRequirements


def format_money(value: Decimal | int | None) -> str:
    if value is None:
        return "not stated"
    return f"{Decimal(value):,.0f} JOD"


def full_years(start: date, end: date) -> int:
    years = end.year - start.year
    if (end.month, end.day) < (start.month, start.day):
        years -= 1
    return max(years, 0)


class QualificationRule(ABC):
    """A single deterministic check of one profile against one tender."""

    rule_id: str = "rule"
    # Tender fields the rule reads. Used to catch requirements that could not be verified.
    fields: tuple[str, ...] = ()

    @abstractmethod
    def evaluate(
        self,
        profile: CompanyProfile,
        tender: TenderRequirements,
        as_of: date,
    ) -> RuleResult:
        raise NotImplementedError

    def _result(
        self,
        status: RuleStatus,
        message: str,
        required: str | None = None,
        actual: str | None = None,
        remediable: bool = False,
    ) -> RuleResult:
        return RuleResult(
            rule_id=self.rule_id,
            status=status,
            message=message,
            required=required,
            actual=actual,
            remediable=remediable,
        )

    def passed(
        self, message: str, required: str | None = None, actual: str | None = None
    ) -> RuleResult:
        return self._result(RuleStatus.PASSED, message, required, actual)

    def failed(
        self,
        message: str,
        required: str | None = None,
        actual: str | None = None,
        remediable: bool = False,
    ) -> RuleResult:
        return self._result(RuleStatus.FAILED, message, required, actual, remediable)

    def unknown(self, message: str, required: str | None = None) -> RuleResult:
        return self._result(RuleStatus.UNKNOWN, message, required, "not stated in profile", True)

    def not_applicable(self, message: str) -> RuleResult:
        return self._result(RuleStatus.NOT_APPLICABLE, message)
