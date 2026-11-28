import copy
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.domain.enums import ClassificationGrade, Verdict, WorkCategory
from app.domain.rules import QualificationEngine
from app.extraction import TenderExtractor
from app.extraction.verify import compact, number_in_quote, quote_on_page
from app.ingestion import read_pdf
from tests.fake_llm import SAMPLE_RESPONSE, FakeLLM

SAMPLE = Path(__file__).parent / "fixtures" / "sample_tender.pdf"


@pytest.fixture(scope="module")
def document():
    return read_pdf(SAMPLE.read_bytes(), "sample_tender.pdf")


def _extract(document, response):
    return TenderExtractor(FakeLLM(response), model_name="fake").extract(document)


def test_extracts_every_requirement(document):
    result = _extract(document, SAMPLE_RESPONSE)
    req = result.requirements

    assert result.rejected == []
    assert req.reference == "ZM-2026-014"
    assert req.work_category is WorkCategory.BUILDINGS
    assert req.required_classification_grade is ClassificationGrade.GRADE_3
    assert req.min_registered_capital == Decimal("100000")
    assert req.min_similar_projects == 2
    assert req.min_similar_project_value == Decimal("250000")
    assert req.min_years_experience == 3
    assert req.submission_deadline == date(2026, 10, 15)
    assert req.bid_guarantee_amount == Decimal("20000")


def test_every_kept_value_has_a_citation(document):
    result = _extract(document, SAMPLE_RESPONSE)
    assert result.citations["min_registered_capital"].page == 2
    assert result.citations["bid_guarantee_amount"].page == 3
    assert len(result.required_documents) == 2


def test_invented_quote_is_rejected(document):
    response = copy.deepcopy(SAMPLE_RESPONSE)
    response["fields"]["min_registered_capital"] = {
        "value": 500000,
        "page": 2,
        "quote": "يجب ألا يقل رأس المال عن 500,000 دينار",
    }
    result = _extract(document, response)

    assert result.requirements.min_registered_capital is None
    assert [r.field for r in result.rejected] == ["min_registered_capital"]


def test_amount_must_match_its_quote(document):
    response = copy.deepcopy(SAMPLE_RESPONSE)
    response["fields"]["bid_guarantee_amount"]["value"] = 25000
    result = _extract(document, response)

    assert result.requirements.bid_guarantee_amount is None
    assert result.rejected[0].reason == "amount does not appear in the quote"


def test_wrong_page_is_rejected(document):
    response = copy.deepcopy(SAMPLE_RESPONSE)
    response["fields"]["min_registered_capital"]["page"] = 4
    result = _extract(document, response)
    assert result.requirements.min_registered_capital is None


def test_invalid_value_type_is_rejected(document):
    response = copy.deepcopy(SAMPLE_RESPONSE)
    response["fields"]["min_similar_projects"]["value"] = "two"
    result = _extract(document, response)

    assert result.requirements.min_similar_projects is None
    assert "min_similar_projects" not in result.citations
    assert result.rejected[0].reason == "value has the wrong type"


def test_grade_must_match_its_quote(document):
    response = copy.deepcopy(SAMPLE_RESPONSE)
    response["fields"]["required_classification_grade"]["value"] = 1
    result = _extract(document, response)
    assert result.requirements.required_classification_grade is None
    assert result.rejected[0].reason == "grade does not match the quote"


def test_category_must_match_its_quote(document):
    response = copy.deepcopy(SAMPLE_RESPONSE)
    response["fields"]["work_category"]["value"] = "roads"
    result = _extract(document, response)
    assert result.requirements.work_category is None
    assert result.rejected[0].reason == "work category does not match the quote"


def test_rejected_field_keeps_the_model_quote(document):
    response = copy.deepcopy(SAMPLE_RESPONSE)
    response["fields"]["min_registered_capital"]["quote"] = "رأس المال لا يقل عن 100,000 دينار"
    rejected = _extract(document, response).rejected[0]
    assert rejected.page == 2
    assert rejected.quote == "رأس المال لا يقل عن 100,000 دينار"


def test_unknown_fields_are_ignored(document):
    response = copy.deepcopy(SAMPLE_RESPONSE)
    response["fields"]["favourite_colour"] = {"value": "blue", "page": 1, "quote": "x"}
    assert _extract(document, response).rejected == []


def test_missing_reference_falls_back_to_filename(document):
    response = copy.deepcopy(SAMPLE_RESPONSE)
    del response["fields"]["reference"]
    assert _extract(document, response).requirements.reference == "sample_tender.pdf"


def test_prompt_carries_page_markers(document):
    llm = FakeLLM(SAMPLE_RESPONSE)
    TenderExtractor(llm).extract(document)
    _, user = llm.calls[0]
    assert "[page 1]" in user
    assert "[page 4]" in user


def test_extraction_feeds_the_rule_engine(document, profile):
    requirements = _extract(document, SAMPLE_RESPONSE).requirements
    report = QualificationEngine().evaluate(profile, requirements, date(2026, 9, 2))
    assert report.verdict is Verdict.QUALIFIED


def test_reversed_lam_alef_still_matches():
    assert quote_on_page("خبرة لا تقل عن ثلاث سنوات", "خبرة ال تقل عن ثالث سنوات")
    assert compact("الأولى") == compact("األولى")


def test_short_quotes_do_not_match_by_accident():
    assert not quote_on_page("في", "في هذا العطاء")


# Quotes returned by openai/gpt-oss-120b on Groq for the sample tender.
GROQ_GRADE_QUOTES = [
    "المقاولين الأردنيين المصنفين لدى دائرة العطاءات الحكومية في مجال الأبنية "
    "بالفئة الثالثة أو أعلى",
    "المقاولين األردنيين المصنفين لدى دائرة العطاءات الحكومية في .مجال األبنية "
    "بالفئة الثالثة أو أعلى",
]


@pytest.mark.parametrize("quote", GROQ_GRADE_QUOTES)
def test_real_model_quotes_are_accepted(document, quote):
    assert quote_on_page(quote, document.pages[1].text)


@pytest.mark.parametrize(
    "quote",
    [
        "المقاولين الأردنيين المصنفين لدى دائرة العطاءات الحكومية في مجال الأبنية "
        "بالفئة الأولى أو أعلى",
        "المقاولين الأردنيين المصنفين لدى دائرة العطاءات الحكومية في مجال الطرق "
        "بالفئة الثالثة أو أعلى",
        "رأس المال لا يقل عن 100,000 دينار",
    ],
)
def test_changed_words_are_rejected(document, quote):
    assert not quote_on_page(quote, document.pages[1].text)


def test_word_split_by_the_pdf_still_matches(document):
    assert quote_on_page("المادة الثانية الكفالات", document.pages[2].text)


def test_number_in_quote():
    assert number_in_quote(100000, "عن 100,000 دينار")
    assert not number_in_quote(150000, "عن 100,000 دينار")


def test_rejected_requirement_makes_verdict_conditional(document, profile):
    response = copy.deepcopy(SAMPLE_RESPONSE)
    response["fields"]["min_registered_capital"]["quote"] = "رأس المال لا يقل عن 100,000 دينار"
    requirements = _extract(document, response).requirements

    assert requirements.unverified_fields == ["min_registered_capital"]
    report = QualificationEngine().evaluate(profile, requirements, date(2026, 9, 2))
    assert report.verdict is Verdict.CONDITIONALLY_QUALIFIED


def test_quote_with_arabic_indic_digits_matches_normalized_page():
    assert quote_on_page("آخر موعد لتقديم العروض ٢٠٢٦/١٢/٢٤", "آخر موعد لتقديم العروض\n2026/12/24")


# Short quotes returned by openai/gpt-oss-120b on the eval set.
def test_short_real_quotes_match():
    roads = "شروط االشتراك\n. في مجال الطرق بالفئة الثانية فما فوقاأن يكون المقاول مصنف"
    assert quote_on_page("بـ الفئة الثانية فما فوق", roads)
    assert not quote_on_page("بـ الفئة الأولى فما فوق", roads)
    assert quote_on_page("2026/12/24", "آخر موعد لتقديم العروض\n2026/12/24")
    assert not quote_on_page("2026/12/25", "آخر موعد لتقديم العروض\n2026/12/24")


def test_deadline_must_match_its_quote(document):
    response = copy.deepcopy(SAMPLE_RESPONSE)
    response["fields"]["submission_deadline"]["value"] = "2026-10-16"
    result = _extract(document, response)
    assert result.requirements.submission_deadline is None
    assert result.rejected[0].reason == "date does not appear in the quote"


def test_date_in_quote():
    from app.extraction.verify import date_in_quote

    assert date_in_quote("2026-10-15", "من يوم 2026/10/15")
    assert date_in_quote("2026-10-15", "بتاريخ 15/10/2026")
    assert date_in_quote("2026-12-24", "٢٠٢٦/١٢/٢٤")
    assert not date_in_quote("2026-10-15", "من يوم 2026/10/16")


def test_cut_off_amount_is_rejected():
    from app.ingestion import ExtractedDocument, PageSource, PageText

    document = ExtractedDocument(
        filename="scan.pdf",
        page_count=1,
        pages=[
            PageText(
                page_number=1,
                source=PageSource.OCR,
                text="قيمة كل منها\n0 دينار أردني على الأقل.",
            )
        ],
    )
    response = {
        "fields": {
            "min_similar_project_value": {
                "value": 0,
                "page": 1,
                "quote": "0 دينار أردني على الأقل",
            }
        }
    }
    result = _extract(document, response)
    assert result.requirements.min_similar_project_value is None
    assert result.rejected[0].reason == "amount is implausibly small"


def test_category_word_with_attached_waw():
    from app.extraction.verify import category_in_quote

    quote = "مصنفا في مجال المباه والصرف الصحي بالفئة الثانية"
    assert category_in_quote("water_and_sewerage", quote)
    assert not category_in_quote("roads", quote)


def test_category_keyword_starting_with_prefix_letter():
    from app.extraction.verify import category_in_quote

    clean = "يقتصر الاشتراك على المقاولين المصنفين في مجال الأعمال الكهروميكانيكية بالفئة الأولى"
    reversed_ligature = ".يقتصر االشتراك على المقاولين المصنفين في مجال األعمال الكهروميكانيكية"
    for quote in (clean, reversed_ligature):
        assert category_in_quote("electromechanical", quote)
        assert not category_in_quote("buildings", quote)


def test_grade_words():
    from app.extraction.verify import grade_in_quote

    assert grade_in_quote(1, "مصنفين بالفئة الأولى")
    assert grade_in_quote(3, "من الفئة الثالثة")
    assert not grade_in_quote(3, "بالفئة الرابعة")
