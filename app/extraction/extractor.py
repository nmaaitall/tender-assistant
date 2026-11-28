"""Turns a tender document into TenderRequirements.

The model proposes values with citations. A value is kept only when its quote is
found on the cited page and the value agrees with the quote. Requirements that are
missing or rejected after the first reading are asked for once more. A requirement
that is still missing but clearly mentioned in the document is marked unverified,
so no rule can pass on it.
"""

from __future__ import annotations

from typing import Any

from pydantic import TypeAdapter, ValidationError

from app.domain.tender import TenderRequirements
from app.extraction.llm import LLMClient
from app.extraction.models import Citation, ExtractionResult, RejectedField, RequiredDocument
from app.extraction.prompt import FIELDS, SYSTEM_PROMPT, build_retry_prompt, build_user_prompt
from app.extraction.verify import (
    category_in_quote,
    date_in_quote,
    grade_in_quote,
    mentioned,
    number_in_quote,
    quote_on_page,
)
from app.ingestion import ExtractedDocument

MONEY_FIELDS = {"min_registered_capital", "min_similar_project_value", "bid_guarantee_amount"}
# Smaller amounts are not real tender requirements; they come from cut-off or misread numbers.
MIN_PLAUSIBLE_AMOUNT = 100
REQUIREMENT_FIELDS = [name for name in FIELDS if name not in ("reference", "title")]


class TenderExtractor:
    def __init__(self, llm: LLMClient, model_name: str = "unknown", second_pass: bool = True):
        self.llm = llm
        self.model_name = model_name
        self.second_pass = second_pass

    def extract(self, document: ExtractedDocument) -> ExtractionResult:
        pages = {p.page_number: p.text for p in document.pages}
        accepted: dict[str, tuple[Any, Citation]] = {}
        rejected: dict[str, RejectedField] = {}

        raw = self.llm.complete_json(SYSTEM_PROMPT, build_user_prompt(document))
        calls = 1
        self._collect(raw.get("fields"), set(FIELDS), pages, accepted, rejected)

        retry = [name for name in REQUIREMENT_FIELDS if name not in accepted]
        if retry and self.second_pass:
            prompt = build_retry_prompt(document, retry, {k: v.reason for k, v in rejected.items()})
            second = self.llm.complete_json(SYSTEM_PROMPT, prompt)
            calls += 1
            self._collect(second.get("fields"), set(retry), pages, accepted, rejected)

        full_text = document.full_text()
        for name in REQUIREMENT_FIELDS:
            if name not in accepted and name not in rejected and mentioned(name, full_text):
                rejected[name] = RejectedField(
                    field=name, reason="mentioned in the document but not extracted"
                )

        values = {name: value for name, (value, _) in accepted.items()}
        values.setdefault("reference", document.filename)
        requirements = TenderRequirements(**values)
        requirements.unverified_fields = sorted(rejected)

        return ExtractionResult(
            requirements=requirements,
            citations={name: citation for name, (_, citation) in accepted.items()},
            required_documents=self._documents(raw.get("required_documents") or [], pages),
            rejected=list(rejected.values()),
            model=self.model_name,
            model_calls=calls,
        )

    def _collect(
        self,
        fields: Any,
        allowed: set[str],
        pages: dict[int, str],
        accepted: dict[str, tuple[Any, Citation]],
        rejected: dict[str, RejectedField],
    ) -> None:
        if not isinstance(fields, dict):
            return
        for name, item in fields.items():
            if name not in allowed or name in accepted:
                continue
            reason = self._check(name, item, pages)
            if reason is None:
                accepted[name] = (item["value"], Citation(page=item["page"], quote=item["quote"]))
                rejected.pop(name, None)
                continue
            cited = item if isinstance(item, dict) else {}
            page, quote = cited.get("page"), cited.get("quote")
            rejected[name] = RejectedField(
                field=name,
                reason=reason,
                page=page if isinstance(page, int) else None,
                quote=quote if isinstance(quote, str) else None,
            )

    def _check(self, name: str, item: Any, pages: dict[int, str]) -> str | None:
        if not isinstance(item, dict) or item.get("value") in (None, ""):
            return "no value"
        page, quote = item.get("page"), item.get("quote")
        if not isinstance(page, int) or page not in pages:
            return "cited page does not exist"
        if not isinstance(quote, str) or not quote_on_page(quote, pages[page]):
            return "quote not found on the cited page"
        if name != "reference":
            try:
                annotation = TenderRequirements.model_fields[name].annotation
                TypeAdapter(annotation).validate_python(item["value"])
            except ValidationError:
                return "value has the wrong type"
        if name == "required_classification_grade" and not (
            isinstance(item["value"], int) and grade_in_quote(item["value"], quote)
        ):
            return "grade does not match the quote"
        if name == "submission_deadline" and not date_in_quote(str(item["value"]), quote):
            return "date does not appear in the quote"
        if name == "work_category" and not category_in_quote(str(item["value"]), quote):
            return "work category does not match the quote"
        if name in MONEY_FIELDS:
            amount = float(item["value"])
            if amount < MIN_PLAUSIBLE_AMOUNT:
                return "amount is implausibly small"
            if not number_in_quote(amount, quote):
                return "amount does not appear in the quote"
        return None

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
