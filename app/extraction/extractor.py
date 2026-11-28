"""Turns a tender document into TenderRequirements.

The model proposes values with citations. A value is kept only when its quote is
found on the cited page, and money amounts must also appear in that quote.
"""

from __future__ import annotations

from typing import Any

from pydantic import TypeAdapter, ValidationError

from app.domain.tender import TenderRequirements
from app.extraction.llm import LLMClient
from app.extraction.models import Citation, ExtractionResult, RejectedField, RequiredDocument
from app.extraction.prompt import FIELDS, SYSTEM_PROMPT, build_user_prompt
from app.extraction.verify import (
    category_in_quote,
    date_in_quote,
    grade_in_quote,
    number_in_quote,
    quote_on_page,
)
from app.ingestion import ExtractedDocument

MONEY_FIELDS = {"min_registered_capital", "min_similar_project_value", "bid_guarantee_amount"}
# Smaller amounts are not real tender requirements; they come from cut-off or misread numbers.
MIN_PLAUSIBLE_AMOUNT = 100


class TenderExtractor:
    def __init__(self, llm: LLMClient, model_name: str = "unknown") -> None:
        self.llm = llm
        self.model_name = model_name

    def extract(self, document: ExtractedDocument) -> ExtractionResult:
        raw = self.llm.complete_json(SYSTEM_PROMPT, build_user_prompt(document))
        pages = {p.page_number: p.text for p in document.pages}

        values: dict[str, Any] = {}
        citations: dict[str, Citation] = {}
        rejected: list[RejectedField] = []

        for name, item in (raw.get("fields") or {}).items():
            if name not in FIELDS:
                continue
            reason = self._check(name, item, pages)
            if reason:
                cited = item if isinstance(item, dict) else {}
                page, quote = cited.get("page"), cited.get("quote")
                rejected.append(
                    RejectedField(
                        field=name,
                        reason=reason,
                        page=page if isinstance(page, int) else None,
                        quote=quote if isinstance(quote, str) else None,
                    )
                )
                continue
            values[name] = item["value"]
            citations[name] = Citation(page=item["page"], quote=item["quote"])

        values.setdefault("reference", document.filename)
        requirements, invalid = self._build_requirements(values)
        for name in invalid:
            citations.pop(name, None)
            rejected.append(RejectedField(field=name, reason="value has the wrong type"))
        requirements.unverified_fields = sorted({r.field for r in rejected})

        return ExtractionResult(
            requirements=requirements,
            citations=citations,
            required_documents=self._documents(raw.get("required_documents") or [], pages),
            rejected=rejected,
            model=self.model_name,
        )

    def _check(self, name: str, item: Any, pages: dict[int, str]) -> str | None:
        if not isinstance(item, dict) or item.get("value") in (None, ""):
            return "no value"
        page, quote = item.get("page"), item.get("quote")
        if not isinstance(page, int) or page not in pages:
            return "cited page does not exist"
        if not isinstance(quote, str) or not quote_on_page(quote, pages[page]):
            return "quote not found on the cited page"
        if name == "required_classification_grade" and not (
            isinstance(item["value"], int) and grade_in_quote(item["value"], quote)
        ):
            return "grade does not match the quote"
        if name == "submission_deadline" and not date_in_quote(str(item["value"]), quote):
            return "date does not appear in the quote"
        if name == "work_category" and not category_in_quote(str(item["value"]), quote):
            return "work category does not match the quote"
        if name in MONEY_FIELDS:
            try:
                amount = float(item["value"])
            except (TypeError, ValueError):
                return "amount is not a number"
            if amount < MIN_PLAUSIBLE_AMOUNT:
                return "amount is implausibly small"
            if not number_in_quote(amount, quote):
                return "amount does not appear in the quote"
        return None

    def _build_requirements(self, values: dict[str, Any]) -> tuple[TenderRequirements, list[str]]:
        invalid: list[str] = []
        fields = TenderRequirements.model_fields
        for name in list(values):
            if name == "reference":
                continue
            try:
                TypeAdapter(fields[name].annotation).validate_python(values[name])
            except ValidationError:
                invalid.append(name)
                values.pop(name)
        return TenderRequirements(**values), invalid

    def _documents(self, items: list[Any], pages: dict[int, str]) -> list[RequiredDocument]:
        documents = []
        for item in items:
            if not isinstance(item, dict) or not item.get("name"):
                continue
            page, quote = item.get("page"), item.get("quote")
            if (
                isinstance(page, int)
                and isinstance(quote, str)
                and quote_on_page(quote, pages.get(page, ""))
            ):
                documents.append(
                    RequiredDocument(name=item["name"], citation=Citation(page=page, quote=quote))
                )
        return documents
