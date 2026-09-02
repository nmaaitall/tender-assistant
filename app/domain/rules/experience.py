from __future__ import annotations

from datetime import date

from app.domain.company import CompanyProfile, PastProject
from app.domain.results import RuleResult
from app.domain.rules.base import QualificationRule, format_money, full_years
from app.domain.tender import TenderRequirements


class ExperienceRule(QualificationRule):
    """Checks years of activity and the count of comparable past projects."""

    rule_id = "experience"

    def evaluate(
        self,
        profile: CompanyProfile,
        tender: TenderRequirements,
        as_of: date,
    ) -> RuleResult:
        if tender.min_years_experience is None and tender.min_similar_projects is None:
            return self.not_applicable("Tender states no experience requirement.")

        if not profile.past_projects:
            return self.unknown(
                "Project history is missing from the profile.",
                self._describe_requirement(tender),
            )

        scoped = self._in_category(profile.past_projects, tender)

        if tender.min_years_experience is not None:
            years = self._years_of_activity(scoped or profile.past_projects, as_of)
            if years < tender.min_years_experience:
                return self.failed(
                    f"Tender requires {tender.min_years_experience} years of experience; "
                    f"company profile shows {years}.",
                    f"at least {tender.min_years_experience} years of experience",
                    f"{years} years",
                    remediable=False,
                )

        if tender.min_similar_projects is not None:
            matching = self._matching_projects(scoped, tender, as_of)
            if len(matching) < tender.min_similar_projects:
                return self.failed(
                    f"Tender requires {tender.min_similar_projects} similar projects "
                    f"within the last {tender.experience_lookback_years} years; "
                    f"company profile shows {len(matching)}.",
                    self._describe_requirement(tender),
                    f"{len(matching)} matching projects",
                    remediable=False,
                )

        return self.passed(
            "Experience requirement met.",
            self._describe_requirement(tender),
            f"{len(profile.past_projects)} projects on file",
        )

    def _in_category(
        self,
        projects: list[PastProject],
        tender: TenderRequirements,
    ) -> list[PastProject]:
        if tender.work_category is None:
            return list(projects)
        return [p for p in projects if p.category == tender.work_category]

    def _years_of_activity(self, projects: list[PastProject], as_of: date) -> int:
        earliest = min(p.completed_on for p in projects)
        return full_years(earliest, as_of)

    def _matching_projects(
        self,
        projects: list[PastProject],
        tender: TenderRequirements,
        as_of: date,
    ) -> list[PastProject]:
        cutoff_year = as_of.year - tender.experience_lookback_years
        cutoff = date(cutoff_year, as_of.month, as_of.day)
        minimum_value = tender.min_similar_project_value
        return [
            p
            for p in projects
            if p.completed_on >= cutoff and (minimum_value is None or p.value >= minimum_value)
        ]

    def _describe_requirement(self, tender: TenderRequirements) -> str:
        parts: list[str] = []
        if tender.min_years_experience is not None:
            parts.append(f"at least {tender.min_years_experience} years of experience")
        if tender.min_similar_projects is not None:
            detail = (
                f"{tender.min_similar_projects} similar projects in the last "
                f"{tender.experience_lookback_years} years"
            )
            if tender.min_similar_project_value is not None:
                detail += f" of {format_money(tender.min_similar_project_value)} or more"
            parts.append(detail)
        return "; ".join(parts) if parts else "no experience requirement"
