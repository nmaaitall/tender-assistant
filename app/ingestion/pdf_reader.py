"""Read a tender PDF page by page and decide which pages need OCR.

No OCR and no model call happens here. Pages without a usable text layer are
flagged so the OCR step can pick them up.
"""

from __future__ import annotations

import pymupdf

from app.ingestion.models import ExtractedDocument, OcrReason, PageSource, PageText
from app.ingestion.text_quality import (
    MAX_GARBLED_RATIO,
    MIN_MEANINGFUL_CHARS,
    garbled_ratio,
    meaningful_char_count,
    normalize_arabic,
)


class PdfReadError(ValueError):
    """The file is not a readable PDF."""


def read_pdf(data: bytes, filename: str = "document.pdf") -> ExtractedDocument:
    try:
        document = pymupdf.open(stream=data, filetype="pdf")
    except (pymupdf.FileDataError, RuntimeError) as exc:
        raise PdfReadError(f"{filename} is not a readable PDF") from exc

    if document.needs_pass:
        document.close()
        raise PdfReadError(f"{filename} is password protected")

    with document:
        pages = [_read_page(page) for page in document]
        return ExtractedDocument(filename=filename, page_count=len(pages), pages=pages)


def _read_page(page: pymupdf.Page) -> PageText:
    number = page.number + 1
    raw = page.get_text("text")
    ratio = garbled_ratio(raw)

    if meaningful_char_count(raw) < MIN_MEANINGFUL_CHARS:
        return PageText(
            page_number=number,
            source=PageSource.NEEDS_OCR,
            ocr_reason=OcrReason.NO_TEXT,
        )

    if ratio > MAX_GARBLED_RATIO:
        return PageText(
            page_number=number,
            source=PageSource.NEEDS_OCR,
            garbled_ratio=ratio,
            ocr_reason=OcrReason.GARBLED_TEXT,
        )

    text = normalize_arabic(raw)
    return PageText(
        page_number=number,
        source=PageSource.TEXT_LAYER,
        text=text,
        char_count=meaningful_char_count(text),
        garbled_ratio=ratio,
    )
