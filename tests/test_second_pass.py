import copy
from datetime import date
from pathlib import Path

import pytest

from app.domain.enums import Verdict
from app.domain.rules import QualificationEngine
from app.extraction import TenderExtractor
from app.ingestion import read_pdf
from tests.fake_llm import SAMPLE_RESPONSE, FakeLLM

FIXTURES = Path(__file__).parent / "fixtures"
EVALS = Path(__file__).resolve().parent.parent / "evals" / "pdfs"


@pytest.fixture(scope="module")
def document():
    return read_pdf((FIXTURES / "sample_tender.pdf").read_bytes(), "sample_tender.pdf")


def _without(*names):
    response = copy.deepcopy(SAMPLE_RESPONSE)
    for name in names:
        del response["fields"][name]
    return response


def _only(*names):
    return {"fields": {n: copy.deepcopy(SAMPLE_RESPONSE["fields"][n]) for n in names}}


def test_complete_first_answer_needs_one_call(document):
    llm = FakeLLM(SAMPLE_RESPONSE)
    result = TenderExtractor(llm).extract(document)
    assert len(llm.calls) == 1
    assert result.model_calls == 1


def test_second_pass_recovers_an_omitted_requirement(document):
    llm = FakeLLM([_without("min_years_experience"), _only("min_years_experience")])
    result = TenderExtractor(llm).extract(document)

    assert result.model_calls == 2
    assert result.requirements.min_years_experience == 3
    assert result.rejected == []
    _, retry_prompt = llm.calls[1]
    assert "min_years_experience" in retry_prompt
    assert "min_registered_capital" not in retry_prompt.split("did not return these fields")[1]


def test_second_pass_retries_a_rejected_value_with_the_reason(document):
    first = copy.deepcopy(SAMPLE_RESPONSE)
    first["fields"]["min_registered_capital"]["quote"] = "رأس المال لا يقل عن 100,000 دينار"
    llm = FakeLLM([first, _only("min_registered_capital")])
    result = TenderExtractor(llm).extract(document)

    assert result.requirements.min_registered_capital == 100000
    assert result.rejected == []
    assert "quote not found on the cited page" in llm.calls[1][1]


def test_second_pass_cannot_change_accepted_values(document):
    second = _only("min_years_experience")
    second["fields"]["min_registered_capital"] = {
        "value": 999999,
        "page": 2,
        "quote": "يجب ألا يقل رأس المال المسجل للمقاول عن 100,000",
    }
    llm = FakeLLM([_without("min_years_experience"), second])
    result = TenderExtractor(llm).extract(document)
    assert result.requirements.min_registered_capital == 100000


def test_requirement_missed_twice_but_mentioned_is_unverified(document, profile):
    response = _without("min_years_experience")
    llm = FakeLLM([response, {"fields": {}}])
    result = TenderExtractor(llm).extract(document)

    assert result.requirements.min_years_experience is None
    assert "min_years_experience" in result.requirements.unverified_fields
    assert result.rejected[0].reason == "mentioned in the document but not extracted"

    report = QualificationEngine().evaluate(profile, result.requirements, date(2026, 9, 2))
    assert report.verdict is Verdict.CONDITIONALLY_QUALIFIED


def test_requirement_not_in_the_document_is_not_flagged():
    document = read_pdf((EVALS / "c05_missing_fields.pdf").read_bytes())
    response = {
        "fields": {
            "work_category": {
                "value": "buildings",
                "page": 2,
                "quote": "يحق الاشتراك للمقاولين المصنفين في مجال الأبنية بالفئة الخامسة أو أعلى.",
            }
        }
    }
    result = TenderExtractor(FakeLLM([response, {"fields": {}}])).extract(document)

    flagged = set(result.requirements.unverified_fields)
    assert "min_registered_capital" not in flagged
    assert "min_similar_projects" not in flagged
    assert "min_years_experience" in flagged


def test_second_pass_can_be_turned_off(document):
    llm = FakeLLM(_without("min_years_experience"))
    result = TenderExtractor(llm, second_pass=False).extract(document)
    assert len(llm.calls) == 1
    assert "min_years_experience" in result.requirements.unverified_fields
