"""Read a tender PDF page by page.

Pages with a usable text layer are read directly. The others are sent to OCR when an
engine is given, and stay flagged as needing OCR when it is not.
"""

from __future__ import annotations

import io
from collections.abc import Callable

import pymupdf
from PIL import Image, ImageFilter

from app.ingestion.models import ExtractedDocument, OcrReason, PageSource, PageText
from app.ingestion.ocr import OcrEngine, OcrError
from app.ingestion.text_quality import (
    MAX_GARBLED_RATIO,
    MIN_MEANINGFUL_CHARS,
    garbled_ratio,
    mark_unreadable_numbers,
    meaningful_char_count,
    normalize_arabic,
)

# Scanned pages are rendered at the resolution of the scan itself; upscaling a
# low-resolution scan magnifies its noise and lowers OCR accuracy.
DEFAULT_SCAN_DPI = 200
MIN_SCAN_DPI = 150
MAX_SCAN_DPI = 300


class PdfReadError(ValueError):
    """The file is not a readable PDF."""


def read_pdf(
    data: bytes,
    filename: str = "document.pdf",
    ocr: OcrEngine | None = None,
    on_page: Callable[[int, int], None] | None = None,
) -> ExtractedDocument:
    """Reads every page. on_page(done, total) is called after each page, for progress."""
    try:
        document = pymupdf.open(stream=data, filetype="pdf")
    except (pymupdf.FileDataError, RuntimeError) as exc:
        raise PdfReadError(f"{filename} is not a readable PDF") from exc

    if document.needs_pass:
        document.close()
        raise PdfReadError(f"{filename} is password protected")

    with document:
        total = document.page_count
        pages = []
        for page in document:
            pages.append(_read_page(page, ocr))
            if on_page is not None:
                on_page(len(pages), total)
        return ExtractedDocument(filename=filename, page_count=len(pages), pages=pages)


def _read_page(page: pymupdf.Page, ocr: OcrEngine | None) -> PageText:
    number = page.number + 1
    raw = page.get_text("text")
    ratio = garbled_ratio(raw)

    if meaningful_char_count(raw) < MIN_MEANINGFUL_CHARS:
        reason = OcrReason.NO_TEXT
    elif ratio > MAX_GARBLED_RATIO:
        reason = OcrReason.GARBLED_TEXT
    else:
        text = normalize_arabic(raw)
        return PageText(
            page_number=number,
            source=PageSource.TEXT_LAYER,
            text=text,
            char_count=meaningful_char_count(text),
            garbled_ratio=ratio,
        )

    if ocr is not None:
        text = _ocr_page(page, ocr)
        if meaningful_char_count(text) >= MIN_MEANINGFUL_CHARS:
            return PageText(
                page_number=number,
                source=PageSource.OCR,
                text=text,
                char_count=meaningful_char_count(text),
                garbled_ratio=garbled_ratio(text),
                ocr_reason=reason,
            )

    return PageText(
        page_number=number,
        source=PageSource.NEEDS_OCR,
        garbled_ratio=ratio,
        ocr_reason=reason,
    )


def _ocr_page(page: pymupdf.Page, ocr: OcrEngine) -> str:
    try:
        return normalize_arabic(mark_unreadable_numbers(ocr.recognize(scan_image(page))))
    except OcrError:
        return ""


def scan_image(page: pymupdf.Page, dpi: int | None = None) -> bytes:
    """Grayscale PNG of the page, with speckle noise removed by a median filter."""
    pixmap = page.get_pixmap(dpi=dpi or scan_dpi(page), colorspace=pymupdf.csGRAY)
    image = Image.open(io.BytesIO(pixmap.tobytes("png"))).filter(ImageFilter.MedianFilter(3))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def scan_dpi(page: pymupdf.Page) -> int:
    """Resolution of the largest image on the page, which is the scan for scanned pages."""
    best = 0.0
    for info in page.get_image_info():
        width_points = info["bbox"][2] - info["bbox"][0]
        if width_points > 0:
            best = max(best, info["width"] / width_points * 72)
    if not best:
        return DEFAULT_SCAN_DPI
    return int(min(max(best, MIN_SCAN_DPI), MAX_SCAN_DPI))
