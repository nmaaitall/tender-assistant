from pathlib import Path

import pytest

from app.domain.tender import TenderRequirements
from app.extraction.models import Citation, ExtractionResult
from app.ingestion import read_pdf
from evals.cases import CASES, FIELDS
from evals.scoring import expected_requirements, outcome, score_case, summarize

PDFS = Path(__file__).resolve().parent.parent / "evals" / "pdfs"
MONEY = ("min_registered_capital", "min_similar_project_value", "bid_guarantee_amount")


def _result(values: dict) -> ExtractionResult:
    present = {k: v for k, v in values.items() if v is not None}
    return ExtractionResult(
        requirements=TenderRequirements(**present),
        citations={k: Citation(page=1, quote="x") for k in present},
        model="test",
    )


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_ground_truth_is_a_valid_requirement_set(case):
    assert set(case["expected"]) == set(FIELDS)
    expected_requirements(case["expected"])


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_pdf_matches_the_case(case):
    document = read_pdf((PDFS / f"{case['id']}.pdf").read_bytes())
    assert document.page_count == len(case["pages"])
    assert document.kind.value == "digital"

    text = document.full_text().replace(",", "")
    for name in MONEY:
        value = case["expected"][name]
        if value is not None:
            assert str(value) in text, f"{name}={value} not in extracted text"


def test_outcomes():
    assert outcome(100000, "100000.00") == "correct"
    assert outcome("buildings", "buildings") == "correct"
    assert outcome("zm-1", "ZM-1 ") == "correct"
    assert outcome(None, None) == "absent"
    assert outcome(5, None) == "missed"
    assert outcome(5, 7) == "wrong"
    assert outcome(None, 7) == "spurious"


def test_perfect_extraction_scores_perfectly():
    case = CASES[0]
    score = score_case(case, _result(case["expected"]))
    assert set(score.outcomes.values()) <= {"correct", "absent"}
    assert score.verdict_matches
    assert score.details == {}


def test_model_defaults_do_not_count_as_extracted():
    case = next(c for c in CASES if c["expected"]["experience_lookback_years"] is None)
    score = score_case(case, _result(case["expected"]))
    assert score.outcomes["experience_lookback_years"] == "absent"


def test_wrong_value_is_counted_as_unsafe():
    case = CASES[0]
    values = dict(case["expected"], min_registered_capital=10000)
    summary = summarize([score_case(case, _result(values))])

    assert summary["unsafe_values"] == 1
    assert summary["per_field"]["min_registered_capital"] == {"wrong": 1}


def test_summary_ratios():
    case = CASES[0]
    values = dict(case["expected"], bid_guarantee_amount=None)
    summary = summarize([score_case(case, _result(values))])

    assert summary["recall"] == round(9 / 10, 4)
    assert summary["precision"] == 1.0
    assert summary["unsafe_values"] == 0
