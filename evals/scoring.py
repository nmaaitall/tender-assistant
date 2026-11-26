"""Compares an extraction with the known answers of a case.

Per field, one of:
- correct: the right value was extracted
- absent: the document does not state the field and nothing was extracted
- missed: the document states it but nothing was extracted (omitted or rejected)
- wrong: a different value was extracted
- spurious: a value was extracted for a field the document does not state

wrong and spurious are the dangerous outcomes, because those values reach the rules.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any

from app.domain.company import Classification, CompanyProfile, PastProject
from app.domain.enums import ClassificationGrade, Verdict, WorkCategory
from app.domain.rules import QualificationEngine
from app.domain.tender import TenderRequirements
from app.extraction import ExtractionResult
from evals.cases import FIELDS

OUTCOMES = ("correct", "absent", "missed", "wrong", "spurious")

AS_OF = date(2026, 11, 1)

# One company is judged against every case, so verdicts can be compared.
PROFILE = CompanyProfile(
    name="Eval Contracting",
    classifications=[
        Classification(category=WorkCategory.BUILDINGS, grade=ClassificationGrade.GRADE_3),
        Classification(category=WorkCategory.ROADS, grade=ClassificationGrade.GRADE_2),
        Classification(category=WorkCategory.WATER_AND_SEWERAGE, grade=ClassificationGrade.GRADE_4),
    ],
    registered_capital=Decimal("200000"),
    past_projects=[
        PastProject(
            title="School extension",
            category=WorkCategory.BUILDINGS,
            value=Decimal("320000"),
            completed_on=date(2023, 5, 10),
        ),
        PastProject(
            title="Municipal offices",
            category=WorkCategory.BUILDINGS,
            value=Decimal("410000"),
            completed_on=date(2024, 11, 1),
        ),
        PastProject(
            title="Warehouse",
            category=WorkCategory.BUILDINGS,
            value=Decimal("150000"),
            completed_on=date(2019, 3, 20),
        ),
        PastProject(
            title="Ring road resurfacing",
            category=WorkCategory.ROADS,
            value=Decimal("450000"),
            completed_on=date(2022, 8, 1),
        ),
        PastProject(
            title="Water network",
            category=WorkCategory.WATER_AND_SEWERAGE,
            value=Decimal("130000"),
            completed_on=date(2025, 2, 15),
        ),
    ],
)


@dataclass
class CaseScore:
    case_id: str
    outcomes: dict[str, str]
    expected_verdict: str
    actual_verdict: str
    rejected: list[dict[str, Any]] = field(default_factory=list)
    details: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def verdict_matches(self) -> bool:
        return self.expected_verdict == self.actual_verdict


def normalize(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Enum):
        value = value.value
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float | Decimal):
        return Decimal(str(value)).normalize()
    text = str(value).strip()
    try:
        return Decimal(text.replace(",", "")).normalize()
    except ArithmeticError:
        return text.upper()


def outcome(expected: Any, actual: Any) -> str:
    expected, actual = normalize(expected), normalize(actual)
    if expected is None:
        return "absent" if actual is None else "spurious"
    if actual is None:
        return "missed"
    return "correct" if expected == actual else "wrong"


def extracted_values(result: ExtractionResult) -> dict[str, Any]:
    """Only fields the model actually returned; defaults on the model do not count."""
    requirements = result.requirements
    return {
        name: getattr(requirements, name) if name in result.citations else None for name in FIELDS
    }


def expected_requirements(expected: dict[str, Any]) -> TenderRequirements:
    values = {k: v for k, v in expected.items() if v is not None}
    return TenderRequirements(**values)


def score_case(case: dict[str, Any], result: ExtractionResult) -> CaseScore:
    actual = extracted_values(result)
    outcomes = {name: outcome(case["expected"][name], actual[name]) for name in FIELDS}
    details = {
        name: {"expected": case["expected"][name], "actual": _plain(actual[name])}
        for name, result_outcome in outcomes.items()
        if result_outcome not in ("correct", "absent")
    }

    engine = QualificationEngine()
    expected_verdict = engine.evaluate(
        PROFILE, expected_requirements(case["expected"]), AS_OF
    ).verdict
    actual_verdict = engine.evaluate(PROFILE, result.requirements, AS_OF).verdict

    return CaseScore(
        case_id=case["id"],
        outcomes=outcomes,
        expected_verdict=Verdict(expected_verdict).value,
        actual_verdict=Verdict(actual_verdict).value,
        rejected=[r.model_dump() for r in result.rejected],
        details=details,
    )


def summarize(scores: list[CaseScore]) -> dict[str, Any]:
    per_field = {name: Counter(s.outcomes[name] for s in scores) for name in FIELDS}
    totals: Counter[str] = Counter()
    for counts in per_field.values():
        totals.update(counts)

    stated = totals["correct"] + totals["missed"] + totals["wrong"]
    extracted = totals["correct"] + totals["wrong"] + totals["spurious"]
    cells = sum(totals.values())
    return {
        "cases": len(scores),
        "field_accuracy": _ratio(totals["correct"] + totals["absent"], cells),
        "recall": _ratio(totals["correct"], stated),
        "precision": _ratio(totals["correct"], extracted),
        "unsafe_values": totals["wrong"] + totals["spurious"],
        "verdict_agreement": _ratio(sum(s.verdict_matches for s in scores), len(scores)),
        "outcomes": dict(totals),
        "per_field": {name: dict(counts) for name, counts in per_field.items()},
    }


def _ratio(part: int, whole: int) -> float:
    return round(part / whole, 4) if whole else 0.0


def _plain(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value
