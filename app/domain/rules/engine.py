from __future__ import annotations

from datetime import date

from app.domain.company import CompanyProfile
from app.domain.enums import RuleStatus, Verdict
from app.domain.results import Gap, QualificationReport, RuleResult
from app.domain.rules.base import QualificationRule
from app.domain.rules.capital import CapitalRule
from app.domain.rules.classification import ClassificationRule
from app.domain.rules.experience import ExperienceRule
from app.domain.tender import TenderRequirements


def default_rules() -> list[QualificationRule]:
    return [ClassificationRule(), ExperienceRule(), CapitalRule()]


class QualificationEngine:
    """Deterministic judge. No model call happens here."""

    def __init__(self, rules: list[QualificationRule] | None = None) -> None:
        self.rules = rules if rules is not None else default_rules()

    def evaluate(
        self,
        profile: CompanyProfile,
        tender: TenderRequirements,
        as_of: date | None = None,
    ) -> QualificationReport:
        evaluated_at = as_of or date.today()
        results = [
            self._guard(rule, rule.evaluate(profile, tender, evaluated_at), tender)
            for rule in self.rules
        ]
        verdict = self._verdict(results)
        gaps = self._gaps(results)
        return QualificationReport(
            tender_reference=tender.reference,
            company_name=profile.name,
            verdict=verdict,
            headline=self._headline(verdict, results),
            evaluated_at=evaluated_at,
            results=results,
            gaps=gaps,
        )

    def _guard(
        self, rule: QualificationRule, result: RuleResult, tender: TenderRequirements
    ) -> RuleResult:
        """A pass cannot rest on a requirement that was dropped as unverifiable."""
        unverified = sorted(set(rule.fields) & set(tender.unverified_fields))
        if not unverified or result.status not in (RuleStatus.PASSED, RuleStatus.NOT_APPLICABLE):
            return result
        return RuleResult(
            rule_id=result.rule_id,
            status=RuleStatus.UNKNOWN,
            message="Could not verify in the tender document: " + ", ".join(unverified) + ".",
            actual="not verified in tender",
        )

    def _verdict(self, results: list[RuleResult]) -> Verdict:
        if any(r.status is RuleStatus.FAILED for r in results):
            return Verdict.NOT_QUALIFIED
        if any(r.status is RuleStatus.UNKNOWN for r in results):
            return Verdict.CONDITIONALLY_QUALIFIED
        return Verdict.QUALIFIED

    def _gaps(self, results: list[RuleResult]) -> list[Gap]:
        return [
            Gap(rule_id=r.rule_id, message=r.message, remediable=r.remediable)
            for r in results
            if r.status in (RuleStatus.FAILED, RuleStatus.UNKNOWN)
        ]

    def _headline(self, verdict: Verdict, results: list[RuleResult]) -> str:
        if verdict is Verdict.NOT_QUALIFIED:
            first = next(r for r in results if r.status is RuleStatus.FAILED)
            return first.message
        if verdict is Verdict.CONDITIONALLY_QUALIFIED:
            return "Cannot confirm qualification yet. " + " ".join(
                r.message for r in results if r.status is RuleStatus.UNKNOWN
            )
        return "Company meets every stated requirement of this tender."
