"""Answers a question about one indexed tender, with citations that are checked.

The question is searched in the tender's passages; the best passages and the
question go to the model, which answers from them only. Before an answer is
returned:

- every cited quote must be found in a passage from the cited page
- every amount or year in the answer (100 or more) must appear in a cited quote;
  small numbers are often written as words in the tender (الفئة الثالثة، ثلاث سنوات)
- an answer without a valid citation is not returned

An answer that fails these checks is reported as unsupported, not shown as fact.
"""

from __future__ import annotations

import re

from app.extraction.llm import LLMClient
from app.extraction.verify import compact_digits, quote_on_page
from app.qa.models import Answer, AnswerStatus, Citation
from app.qa.prompt import SYSTEM_PROMPT, build_prompt
from app.retrieval import ChunkIndex, Hit

PASSAGES = 5
MIN_CHECKED_NUMBER = 100
_NUMBER = re.compile(r"\d[\d,]*")


class TenderQA:
    def __init__(self, llm: LLMClient, index: ChunkIndex, passages: int = PASSAGES) -> None:
        self.llm = llm
        self.index = index
        self.passages = passages

    def ask(self, document_id: str, question: str) -> Answer:
        hits = self.index.search(document_id, question, limit=self.passages)
        pages_read = sorted({h.page for h in hits})
        if not hits:
            return Answer(question=question, status=AnswerStatus.NOT_FOUND, pages_read=[])

        data = self.llm.complete_json(SYSTEM_PROMPT, build_prompt(question, hits))
        text = data.get("answer")
        if not isinstance(text, str) or not text.strip():
            return Answer(question=question, status=AnswerStatus.NOT_FOUND, pages_read=pages_read)

        citations = _valid_citations(data.get("citations"), hits)
        reason = None
        if not citations:
            reason = "no citation was found in the passages"
        elif missing := _numbers_not_cited(text, citations):
            reason = f"numbers not found in the citations: {', '.join(missing)}"
        status = AnswerStatus.UNSUPPORTED if reason else AnswerStatus.ANSWERED
        return Answer(
            question=question,
            status=status,
            answer=text.strip(),
            citations=citations,
            pages_read=pages_read,
            reason=reason,
        )


def _valid_citations(raw: object, hits: list[Hit]) -> list[Citation]:
    if not isinstance(raw, list):
        return []
    valid: list[Citation] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        page, quote = item.get("page"), item.get("quote")
        if not isinstance(page, int) or not isinstance(quote, str) or not quote.strip():
            continue
        if any(h.page == page and quote_on_page(quote, h.text) for h in hits):
            valid.append(Citation(page=page, quote=quote.strip()))
    return valid


def numbers_in(text: str) -> set[str]:
    # Arabic-Indic digits become Western ones; spaces between words are kept.
    western = " ".join(compact_digits(word) for word in text.split())
    return {n.replace(",", "") for n in _NUMBER.findall(western)}


def _numbers_not_cited(answer: str, citations: list[Citation]) -> list[str]:
    cited = set().union(*(numbers_in(c.quote) for c in citations))
    return sorted(n for n in numbers_in(answer) if int(n) >= MIN_CHECKED_NUMBER and n not in cited)
