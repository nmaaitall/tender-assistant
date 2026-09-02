from decimal import Decimal

from app.domain.enums import ClassificationGrade, Verdict
from app.domain.rules import QualificationEngine


def test_qualified_profile(profile, tender, today):
    report = QualificationEngine().evaluate(profile, tender, today)
    assert report.verdict is Verdict.QUALIFIED
    assert report.gaps == []
    assert report.tender_reference == "ZM-2026-014"


def test_not_qualified_reports_first_failure(profile, tender, today):
    profile.classifications[0].grade = ClassificationGrade.GRADE_5
    report = QualificationEngine().evaluate(profile, tender, today)
    assert report.verdict is Verdict.NOT_QUALIFIED
    assert "classification grade 3" in report.headline
    assert [gap.rule_id for gap in report.gaps] == ["classification"]


def test_failure_outranks_missing_data(profile, tender, today):
    profile.registered_capital = None
    profile.classifications[0].grade = ClassificationGrade.GRADE_5
    report = QualificationEngine().evaluate(profile, tender, today)
    assert report.verdict is Verdict.NOT_QUALIFIED
    assert len(report.gaps) == 2


def test_conditional_when_profile_incomplete(profile, tender, today):
    profile.registered_capital = None
    report = QualificationEngine().evaluate(profile, tender, today)
    assert report.verdict is Verdict.CONDITIONALLY_QUALIFIED
    assert report.gaps[0].remediable is True


def test_report_is_serializable(profile, tender, today):
    report = QualificationEngine().evaluate(profile, tender, today)
    payload = report.model_dump(mode="json")
    assert payload["verdict"] == "qualified"
    assert payload["evaluated_at"] == "2026-09-02"


def test_evaluation_is_deterministic(profile, tender, today):
    engine = QualificationEngine()
    first = engine.evaluate(profile, tender, today)
    second = engine.evaluate(profile, tender, today)
    assert first.model_dump() == second.model_dump()


def test_capital_gap_message(profile, tender, today):
    profile.registered_capital = Decimal("60000")
    report = QualificationEngine().evaluate(profile, tender, today)
    assert "100,000 JOD" in report.headline
