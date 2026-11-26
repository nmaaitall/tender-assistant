from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, computed_field


class PageSource(StrEnum):
    """Where the text of a page comes from."""

    TEXT_LAYER = "text_layer"
    NEEDS_OCR = "needs_ocr"


class OcrReason(StrEnum):
    NO_TEXT = "no_text"
    GARBLED_TEXT = "garbled_text"


class DocumentKind(StrEnum):
    DIGITAL = "digital"
    SCANNED = "scanned"
    MIXED = "mixed"


class PageText(BaseModel):
    """One page of a tender document. Page numbers start at 1, as printed."""

    page_number: int = Field(ge=1)
    source: PageSource
    text: str = ""
    char_count: int = Field(default=0, ge=0)
    garbled_ratio: float = Field(default=0.0, ge=0, le=1)
    ocr_reason: OcrReason | None = None


class ExtractedDocument(BaseModel):
    filename: str
    page_count: int = Field(ge=0)
    pages: list[PageText] = Field(default_factory=list)

    @computed_field
    @property
    def ocr_pages(self) -> list[int]:
        return [p.page_number for p in self.pages if p.source is PageSource.NEEDS_OCR]

    @computed_field
    @property
    def kind(self) -> DocumentKind:
        if not self.ocr_pages:
            return DocumentKind.DIGITAL
        if len(self.ocr_pages) == self.page_count:
            return DocumentKind.SCANNED
        return DocumentKind.MIXED

    @property
    def needs_ocr(self) -> bool:
        return bool(self.ocr_pages)

    def full_text(self) -> str:
        """Readable text with page markers, so later steps can cite page numbers."""
        return "\n\n".join(f"[page {p.page_number}]\n{p.text}" for p in self.pages if p.text)
