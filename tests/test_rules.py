from decimal import Decimal

from app.domain.enums import ClassificationGrade, RuleStatus, WorkCategory
from app.domain.rules import CapitalRule, ClassificationRule, ExperienceRule


def test_classification_passes_with_higher_grade(profile, tender, today):
    profile.classifications[0].grade = ClassificationGrade.GRADE_2
    result = ClassificationRule().evaluate(profile, tender, today)
    assert result.status is RuleStatus.PASSED


def test_classification_fails_with_lower_grade(profile, tender, today):
    profile.classifications[0].grade = ClassificationGrade.GRADE_5
    result = ClassificationRule().evaluate(profile, tender, today)
    assert result.status is RuleStatus.FAILED
    assert result.remediable is False


def test_classification_fails_when_category_not_held(profile, tender, today):
    tender.work_category = WorkCategory.ROADS
    result = ClassificationRule().evaluate(profile, tender, today)
    assert result.status is RuleStatus.FAILED


def test_classification_unknown_when_profile_empty(profile, tender, today):
    profile.classifications = []
    result = ClassificationRule().evaluate(profile, tender, today)
    assert result.status is RuleStatus.UNKNOWN


def test_classification_not_applicable(profile, tender, today):
    tender.required_classification_grade = None
    result = ClassificationRule().evaluate(profile, tender, today)
    assert result.status is RuleStatus.NOT_APPLICABLE


def test_capital_passes_on_exact_minimum(profile, tender, today):
    profile.registered_capital = Decimal("100000")
    result = CapitalRule().evaluate(profile, tender, today)
    assert result.status is RuleStatus.PASSED


def test_capital_fails_below_minimum(profile, tender, today):
    profile.registered_capital = Decimal("60000")
    result = CapitalRule().evaluate(profile, tender, today)
    assert result.status is RuleStatus.FAILED
    assert result.remediable is True


def test_capital_unknown_when_missing(profile, tender, today):
    profile.registered_capital = None
    result = CapitalRule().evaluate(profile, tender, today)
    assert result.status is RuleStatus.UNKNOWN


def test_experience_passes(profile, tender, today):
    result = ExperienceRule().evaluate(profile, tender, today)
    assert result.status is RuleStatus.PASSED


def test_experience_fails_on_years(profile, tender, today):
    tender.min_years_experience = 12
    result = ExperienceRule().evaluate(profile, tender, today)
    assert result.status is RuleStatus.FAILED
    assert "12 years" in result.message


def test_experience_ignores_projects_outside_lookback(profile, tender, today):
    tender.min_similar_projects = 3
    result = ExperienceRule().evaluate(profile, tender, today)
    assert result.status is RuleStatus.FAILED


def test_experience_ignores_low_value_projects(profile, tender, today):
    tender.min_similar_project_value = Decimal("400000")
    result = ExperienceRule().evaluate(profile, tender, today)
    assert result.status is RuleStatus.FAILED


def test_experience_ignores_other_categories(profile, tender, today):
    for project in profile.past_projects:
        project.category = WorkCategory.ROADS
    result = ExperienceRule().evaluate(profile, tender, today)
    assert result.status is RuleStatus.FAILED


def test_experience_unknown_without_history(profile, tender, today):
    profile.past_projects = []
    result = ExperienceRule().evaluate(profile, tender, today)
    assert result.status is RuleStatus.UNKNOWN
