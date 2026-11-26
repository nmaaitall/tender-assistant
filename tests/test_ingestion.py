from pathlib import Path

import pymupdf
import pytest

from app.ingestion import DocumentKind, PageSource, PdfReadError, read_pdf
from app.ingestion.models import OcrReason
from app.ingestion.text_quality import garbled_ratio, is_usable, normalize_arabic

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE = FIXTURES / "sample_tender.pdf"

# Real output from a PDF whose font has a broken ToUnicode map.
GARBLED = "ண\nாﺍݿ۰ ﺍܳདྷ๤ﻭﻁ ﻭﺍ৊ৎިﺍݬڰ؇ﺕ. ﺭﺃﺱ ﺍ৊ৎ؇ﻝ ﺍ৊ৎފ༶ܭ لگܭ 100,000"


@pytest.fixture(scope="module")
def sample_bytes() -> bytes:
    return SAMPLE.read_bytes()


def _as_scanned(pdf_bytes: bytes, scanned_pages: set[int] | None = None) -> bytes:
    """Rebuild a PDF where the chosen pages (1-based) are images without a text layer."""
    source = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    output = pymupdf.open()
    for page in source:
        number = page.number + 1
        if scanned_pages is None or number in scanned_pages:
            pixmap = page.get_pixmap(dpi=100)
            new_page = output.new_page(width=page.rect.width, height=page.rect.height)
            new_page.insert_image(new_page.rect, pixmap=pixmap)
        else:
            output.insert_pdf(source, from_page=page.number, to_page=page.number)
    return output.tobytes()


def test_digital_pdf_reads_every_page(sample_bytes):
    document = read_pdf(sample_bytes, "sample_tender.pdf")
    assert document.page_count == 4
    assert document.kind is DocumentKind.DIGITAL
    assert document.ocr_pages == []
    assert all(p.source is PageSource.TEXT_LAYER for p in document.pages)


def test_page_numbers_start_at_one(sample_bytes):
    document = read_pdf(sample_bytes)
    assert [p.page_number for p in document.pages] == [1, 2, 3, 4]


def test_key_requirements_are_in_the_text(sample_bytes):
    document = read_pdf(sample_bytes)
    by_page = {p.page_number: p.text for p in document.pages}
    assert "ZM-2026-014" in by_page[1]
    assert "100,000" in by_page[2]
    assert "250,000" in by_page[2]
    assert "20,000" in by_page[3]
    assert "رأس المال" in by_page[2]


def test_full_text_keeps_page_markers(sample_bytes):
    text = read_pdf(sample_bytes).full_text()
    assert "[page 1]" in text
    assert "[page 4]" in text


def test_scanned_pdf_is_routed_to_ocr(sample_bytes):
    document = read_pdf(_as_scanned(sample_bytes))
    assert document.kind is DocumentKind.SCANNED
    assert document.ocr_pages == [1, 2, 3, 4]
    assert all(p.ocr_reason is OcrReason.NO_TEXT for p in document.pages)


def test_mixed_pdf_flags_only_scanned_pages(sample_bytes):
    document = read_pdf(_as_scanned(sample_bytes, scanned_pages={3}))
    assert document.kind is DocumentKind.MIXED
    assert document.ocr_pages == [3]


def test_invalid_bytes_raise():
    with pytest.raises(PdfReadError):
        read_pdf(b"%PDF-1.7 not really a pdf", "broken.pdf")


def test_garbled_text_is_detected():
    assert garbled_ratio(GARBLED) > 0.15
    assert not is_usable(GARBLED)


def test_clean_arabic_is_usable():
    text = "يجب ألا يقل رأس المال المسجل للمقاول عن 100,000 دينار أردني"
    assert garbled_ratio(text) == 0
    assert is_usable(text)


def test_normalize_converts_presentation_forms():
    assert normalize_arabic("ﻛﺮﺍﺳﺔ ﺍﻟﺸﺮﻭﻁ") == "كراسة الشروط"


def test_normalize_removes_tashkeel_and_tatweel():
    assert normalize_arabic("دينارًا  أردنيـــاً") == "دينارا أردنيا"


def test_normalize_separates_numbers_from_words():
    assert normalize_arabic("عن100,000") == "عن 100,000"


def test_normalize_drops_punctuation_only_lines():
    assert normalize_arabic("سطر أول\n :\n.\nسطر ثان") == "سطر أول\nسطر ثان"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("١٢٠,٠٠٠", "120,000"),
        ("٠٠٠,٠٢١", "120,000"),
        ("٠٠٥,٧", "7,500"),
        ("٢٠٢٦/١٢/٢٤", "2026/12/24"),
        ("٤٢/٢١/٦٢٠٢", "2026/12/24"),
        ("٢٥٠٫٥", "250.5"),
        ("١٥", "15"),
    ],
)
def test_arabic_indic_numbers(raw, expected):
    from app.ingestion.text_quality import western_number

    assert western_number(raw) == expected


def test_reversed_arabic_indic_amount_in_a_sentence():
    assert normalize_arabic("ألا يقل عن ٠٠٠,٠٢١ دينار") == "ألا يقل عن 120,000 دينار"
