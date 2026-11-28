import pytest

from app.classify import CategoryClassifier, encode
from app.classify.features import BUCKETS, MAX_TOKENS, PAD
from app.domain.enums import WorkCategory
from app.ingestion import ExtractedDocument, PageSource, PageText
from app.jobs.tasks import _category_check


def test_encode_pads_and_stays_in_range():
    ids = encode("توريد وتركيب مصاعد كهربائية")
    assert len(ids) == MAX_TOKENS
    assert ids[-1] == PAD
    assert all(0 <= i < BUCKETS for i in ids)
    assert encode("توريد وتركيب مصاعد كهربائية") == ids


def test_encode_shares_pieces_between_word_forms():
    a = {i for i in encode("مضخات") if i != PAD}
    b = {i for i in encode("مضخة") if i != PAD}
    assert a & b


def test_encode_truncates_long_text():
    assert len(encode("كلمة " * 1000)) == MAX_TOKENS


@pytest.fixture(scope="module")
def classifier():
    if not CategoryClassifier.available():
        pytest.skip("no exported model")
    return CategoryClassifier()


def test_classifier_predicts_a_clear_case(classifier):
    prediction = classifier.predict("توريد وتركيب مصاعد ومضخات حريق لمبنى المستشفى")
    assert prediction.category == "electromechanical"
    assert abs(sum(prediction.scores.values()) - 1) < 0.01


def _document(text):
    return ExtractedDocument(
        filename="t.pdf",
        page_count=1,
        pages=[PageText(page_number=1, source=PageSource.TEXT_LAYER, text=text)],
    )


def test_confident_disagreement_is_flagged(classifier):
    check = _category_check(_document("توريد وتركيب مصاعد ومضخات حريق"), WorkCategory.ROADS)
    assert check["extracted"] == "roads"
    assert check["flagged"] is (check["confidence"] >= 0.7)


def test_no_flag_without_an_extracted_category(classifier):
    check = _category_check(_document("توريد وتركيب مصاعد"), None)
    assert check["flagged"] is False
