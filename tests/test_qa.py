from qdrant_client import QdrantClient

from app.ingestion import ExtractedDocument, PageSource, PageText
from app.qa import Answer, AnswerStatus, Citation, TenderQA
from app.retrieval import ChunkIndex, chunk_document
from evals.qa import score_answer, value_in_answer
from tests.fake_llm import FakeLLM

PAGES = [
    "آخر موعد لتقديم العروض يوم 2026/10/15",
    "يقدم المقاول مع عرضه كفالة دخول عطاء بقيمة 20,000 دينار أردني.",
    "يلتزم المقاول الفائز بتقديم كفالة حسن تنفيذ بنسبة 10% من قيمة العقد.",
]


def _qa(response) -> tuple[TenderQA, FakeLLM]:
    document = ExtractedDocument(
        filename="t.pdf",
        page_count=len(PAGES),
        pages=[
            PageText(page_number=i, source=PageSource.TEXT_LAYER, text=text)
            for i, text in enumerate(PAGES, start=1)
        ],
    )
    index = ChunkIndex(QdrantClient(":memory:"))
    index.add("t", chunk_document(document))
    llm = FakeLLM(response)
    return TenderQA(llm, index), llm


def test_answer_with_a_valid_citation():
    qa, llm = _qa(
        {
            "answer": "قيمة كفالة دخول العطاء 20,000 دينار أردني.",
            "citations": [{"page": 2, "quote": "كفالة دخول عطاء بقيمة 20,000 دينار أردني"}],
        }
    )
    answer = qa.ask("t", "ما قيمة كفالة دخول العطاء؟")

    assert answer.status is AnswerStatus.ANSWERED
    assert answer.citations[0].page == 2
    assert 2 in answer.pages_read
    assert "[صفحة 2]" in llm.calls[0][1]


def test_quote_from_the_wrong_page_is_dropped():
    qa, _ = _qa(
        {
            "answer": "قيمة الكفالة 20,000 دينار.",
            "citations": [{"page": 3, "quote": "كفالة دخول عطاء بقيمة 20,000 دينار أردني"}],
        }
    )
    answer = qa.ask("t", "ما قيمة كفالة دخول العطاء؟")
    assert answer.status is AnswerStatus.UNSUPPORTED
    assert answer.citations == []


def test_amount_missing_from_the_citations_is_unsupported():
    qa, _ = _qa(
        {
            "answer": "قيمة الكفالة 25,000 دينار.",
            "citations": [{"page": 2, "quote": "كفالة دخول عطاء بقيمة 20,000 دينار أردني"}],
        }
    )
    answer = qa.ask("t", "ما قيمة كفالة دخول العطاء؟")
    assert answer.status is AnswerStatus.UNSUPPORTED
    assert "25000" in answer.reason


def test_null_answer_is_not_found():
    qa, _ = _qa({"answer": None, "citations": []})
    assert qa.ask("t", "ما قيمة كفالة دخول العطاء؟").status is AnswerStatus.NOT_FOUND


def test_no_matching_passage_skips_the_model():
    qa, llm = _qa({"answer": "x", "citations": []})
    answer = qa.ask("t", "سؤال لا علاقة له")
    assert answer.status is AnswerStatus.NOT_FOUND
    assert llm.calls == []


def test_value_in_answer():
    assert value_in_answer("bid_guarantee_amount", 20000, "الكفالة 20,000 دينار")
    assert value_in_answer("submission_deadline", "2026-10-15", "يوم 2026/10/15")
    assert value_in_answer("min_years_experience", 3, "ثلاث سنوات على الأقل")
    assert value_in_answer("min_similar_projects", 1, "أنجزت عملاً واحداً مماثلاً")
    assert value_in_answer("min_similar_projects", 2, "عملين سابقين مشابهين")
    assert not value_in_answer("min_similar_projects", 2, "ثلاثة مشاريع")
    assert value_in_answer("required_classification_grade", 2, "الفئة الثانية")
    assert value_in_answer("work_category", "roads", "مجال الطرق")
    assert not value_in_answer("bid_guarantee_amount", 20000, "10% من قيمة العقد")


def test_score_answer():
    answered = Answer(
        question="q",
        status=AnswerStatus.ANSWERED,
        answer="الكفالة 20,000 دينار",
        citations=[Citation(page=2, quote="...")],
    )
    refused = Answer(question="q", status=AnswerStatus.NOT_FOUND)

    assert score_answer(answered, 20000, "bid_guarantee_amount", {2}) == "correct"
    assert score_answer(answered, 20000, "bid_guarantee_amount", {3}) == "wrong"
    assert score_answer(refused, 20000, "bid_guarantee_amount", {2}) == "missed"
    assert score_answer(answered, None, None, set()) == "invented"
    assert score_answer(refused, None, "bid_guarantee_amount", set()) == "refused"


def test_numbers_in_reads_grouped_thousands():
    from app.qa.answerer import numbers_in

    assert numbers_in("100 000 دينار و 20,000 دينار و ٢٠٢٦/١٠/١٥") >= {"100000", "20000", "2026"}
    assert "100" not in numbers_in("100 000 دينار")
