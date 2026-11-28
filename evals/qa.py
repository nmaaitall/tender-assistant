"""Measures question answering over the eval tenders.

Every tender, with general contract conditions added, is indexed. For each
requirement a question is asked; requirements the tender does not state, and two
questions about things no tender states, must come back as not found.

Each answer is scored as:
- correct: answered, the value is in the answer and a citation is on the right page
- wrong: answered with another value, or citing the wrong page
- missed: not found or unsupported although the tender states it
- refused: correctly not answered, for a question the tender does not answer
- invented: answered a question the tender does not answer

Wrong and invented answers are the unsafe ones. Unsupported answers (failed the
citation check) are never shown as fact, so they count as missed or refused.

Usage:
    python -m evals.qa                    hybrid search with reranking
    python -m evals.qa --lexical          lexical search only, no model download
    python -m evals.qa --paraphrase       paraphrased questions
    python -m evals.qa --cases c01_baseline c10_arabic_digits
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from qdrant_client import QdrantClient

from app.config import settings
from app.extraction import GroqClient, LLMError
from app.extraction.verify import category_in_quote, compact, date_in_quote, grade_in_quote
from app.ingestion import read_pdf
from app.qa import Answer, AnswerStatus, TenderQA
from app.qa.answerer import numbers_in
from app.retrieval import ChunkIndex, FastEmbedEmbedder, FastEmbedReranker, chunk_document
from evals.cases import CASES
from evals.retrieval import QUESTIONS, with_boilerplate

ROOT = Path(__file__).resolve().parent
PDFS = ROOT / "pdfs"
RESULTS = ROOT / "results"

UNANSWERABLE = (
    "ما هو ثمن نسخة كراسة الشروط؟",
    "هل يسمح بتقديم عروض بديلة؟",
)
SAFE = {"correct", "missed", "refused"}

_COUNT_WORDS = {
    1: ("واحد", "واحدة", "سنة"),
    2: ("اثنان", "اثنين", "اثنتين", "مشروعين", "عملين", "سنتين", "عامين"),
    3: ("ثلاث", "ثلاثة"),
    4: ("أربع", "أربعة"),
    5: ("خمس", "خمسة"),
    6: ("ست", "ستة"),
    7: ("سبع", "سبعة"),
    8: ("ثماني", "ثمانية"),
    9: ("تسع", "تسعة"),
    10: ("عشر", "عشرة"),
}


def value_in_answer(field: str, value: Any, answer: str) -> bool:
    if field == "work_category":
        return category_in_quote(value, answer)
    if field == "submission_deadline":
        return date_in_quote(value, answer)
    if field == "required_classification_grade":
        return grade_in_quote(value, answer) or str(value) in numbers_in(answer)
    number = str(int(value))
    if number in numbers_in(answer):
        return True
    words = {compact(w) for w in answer.split()}
    # Accusative and feminine endings: واحدا، ثلاثة.
    forms = {compact(w) + end for w in _COUNT_WORDS.get(int(value), ()) for end in ("", "ا", "ه")}
    return bool(words & forms)


def gold_pages(case: dict, evidence: tuple[str, ...]) -> set[int]:
    return {
        i
        for i, lines in enumerate(case["pages"], start=1)
        if any(compact(word) in compact(" ".join(lines)) for word in evidence)
    }


def score_answer(answer: Answer, expected: Any, field: str | None, pages: set[int]) -> str:
    answered = answer.status is AnswerStatus.ANSWERED
    if field is None or expected is None:
        return "invented" if answered else "refused"
    if not answered:
        return "missed"
    cited_pages = {c.page for c in answer.citations}
    if value_in_answer(field, expected, answer.answer or "") and cited_pages & pages:
        return "correct"
    return "wrong"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=settings.groq_model)
    parser.add_argument("--cases", nargs="*", help="case ids to run (default: all)")
    parser.add_argument("--lexical", action="store_true", help="lexical search only")
    parser.add_argument("--paraphrase", action="store_true", help="paraphrased questions")
    parser.add_argument("--delay", type=float, default=5.0, help="seconds between calls")
    args = parser.parse_args()

    if not settings.groq_api_key:
        raise SystemExit("Set GROQ_API_KEY in .env first.")
    embedder = None if args.lexical else FastEmbedEmbedder()
    reranker = None if args.lexical else FastEmbedReranker()
    index = ChunkIndex(QdrantClient(":memory:"), embedder, reranker=reranker)
    qa = TenderQA(
        GroqClient(settings.groq_api_key, args.model, settings.llm_timeout_seconds), index
    )

    rows: list[dict[str, Any]] = []
    failures = 0
    for case in (c for c in CASES if not args.cases or c["id"] in args.cases):
        document = read_pdf((PDFS / f"{case['id']}.pdf").read_bytes(), case["id"])
        index.add(case["id"], chunk_document(with_boilerplate(document)))
        questions: list[tuple[str | None, str, tuple[str, ...]]] = [
            (field, paraphrase if args.paraphrase else wording, evidence)
            for field, (wording, paraphrase, evidence) in QUESTIONS.items()
        ]
        questions += [(None, q, ()) for q in UNANSWERABLE]

        marks = ""
        for field, question, evidence in questions:
            time.sleep(args.delay)
            expected = case["expected"][field] if field else None
            try:
                answer = qa.ask(case["id"], question)
            except LLMError as exc:
                failures += 1
                marks += "!"
                rows.append({"case": case["id"], "field": field, "error": str(exc)})
                continue
            outcome = score_answer(answer, expected, field, gold_pages(case, evidence))
            marks += outcome[0].upper() if outcome not in ("correct", "refused") else "."
            rows.append(
                {
                    "case": case["id"],
                    "field": field,
                    "question": question,
                    "expected": expected,
                    "outcome": outcome,
                    "answer": answer.model_dump(mode="json"),
                }
            )
        print(f"{case['id']:<24} {marks}")

    scored = [r for r in rows if "outcome" in r]
    counts = Counter(r["outcome"] for r in scored)
    answerable = counts["correct"] + counts["wrong"] + counts["missed"]
    unanswerable = counts["refused"] + counts["invented"]
    summary = {
        "questions": len(scored),
        "failed_calls": failures,
        "outcomes": dict(counts),
        "answer_accuracy": round(counts["correct"] / answerable, 4) if answerable else None,
        "refusal_rate": round(counts["refused"] / unanswerable, 4) if unanswerable else None,
        "unsafe_answers": counts["wrong"] + counts["invented"],
        "unsupported": sum(1 for r in scored if r["answer"]["status"] == "unsupported"),
    }

    print("\nLegend: . correct or refused  W wrong  M missed  I invented  ! failed call")
    print(f"Answer accuracy   {summary['answer_accuracy']:.1%}  ({answerable} questions)")
    print(f"Refusals          {summary['refusal_rate']:.1%}  ({unanswerable} questions)")
    print(f"Unsafe answers    {summary['unsafe_answers']}")
    print(f"Unsupported       {summary['unsupported']}  (failed the citation check)")
    print(f"Failed calls      {failures}")
    errors = [r["error"] for r in rows if "error" in r]
    if errors:
        print(f"  first error: {errors[0]}")
    for r in scored:
        if r["outcome"] not in SAFE or r["outcome"] == "missed":
            a = r["answer"]
            print(f"\n{r['case']} {r['field']} {r['outcome']}: {r['question']}")
            print(f"  expected {r['expected']}, got {a['status']}: {a['answer']}")
            if a["reason"]:
                print(f"  {a['reason']}")

    RESULTS.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    name = "qa_" + args.model.replace("/", "_") + ("_paraphrase" if args.paraphrase else "")
    path = RESULTS / f"{stamp}_{name}.json"
    path.write_text(
        json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nSaved {path.relative_to(ROOT.parent)}")


if __name__ == "__main__":
    main()
