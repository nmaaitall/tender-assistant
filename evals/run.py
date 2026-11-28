"""Runs the extraction pipeline on every eval case and scores it.

Usage:
    python -m evals.run
    python -m evals.run --cases c01_baseline c06_distractors
    python -m evals.run --model openai/gpt-oss-20b
    python -m evals.run --scanned        (scanned copies, read by OCR)
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from app.config import settings
from app.extraction import GroqClient, LLMError, TenderExtractor
from app.ingestion import TesseractOcr, read_pdf
from evals.cases import CASES, FIELDS
from evals.scoring import OUTCOMES, CaseScore, score_case, summarize

ROOT = Path(__file__).resolve().parent
PDFS = ROOT / "pdfs"
RESULTS = ROOT / "results"

SYMBOLS = {"correct": ".", "absent": "-", "missed": "M", "wrong": "W", "spurious": "S"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=settings.groq_model)
    parser.add_argument("--cases", nargs="*", help="case ids to run (default: all)")
    parser.add_argument("--delay", type=float, default=5.0, help="seconds between calls")
    parser.add_argument("--scanned", action="store_true", help="use the scanned copies")
    args = parser.parse_args()

    if not settings.groq_api_key:
        raise SystemExit("Set GROQ_API_KEY in .env first.")
    if args.scanned and not TesseractOcr.available():
        raise SystemExit("Tesseract is not installed: brew install tesseract tesseract-lang")
    source = PDFS / "scanned" if args.scanned else PDFS
    ocr = TesseractOcr() if args.scanned else None

    cases = [c for c in CASES if not args.cases or c["id"] in args.cases]
    extractor = TenderExtractor(
        GroqClient(settings.groq_api_key, args.model, settings.llm_timeout_seconds),
        model_name=args.model,
    )

    scores: list[CaseScore] = []
    failures: dict[str, str] = {}
    for index, case in enumerate(cases):
        if index:
            time.sleep(args.delay)
        document = read_pdf(
            (source / f"{case['id']}.pdf").read_bytes(), f"{case['id']}.pdf", ocr=ocr
        )
        try:
            result = extractor.extract(document)
        except LLMError as exc:
            failures[case["id"]] = str(exc)
            print(f"{case['id']:<24} FAILED  {exc}")
            continue
        score = score_case(case, result)
        scores.append(score)
        print(_case_line(score))

    summary = summarize(scores)
    _print_summary(summary, failures)
    _save(args.model + ("_scanned" if args.scanned else ""), summary, scores, failures)


def _case_line(score: CaseScore) -> str:
    marks = "".join(SYMBOLS[score.outcomes[name]] for name in FIELDS)
    verdict = {"match": "ok ", "cautious": "CAU", "wrong": "BAD"}[score.verdict_outcome]
    line = f"{score.case_id:<24} {marks}  verdict {verdict} ({score.actual_verdict})"
    for name, detail in score.details.items():
        line += f"\n{'':<26}{name}: expected {detail['expected']}, got {detail['actual']}"
    for item in score.rejected:
        line += f"\n{'':<26}rejected {item['field']}: {item['reason']}"
        if item.get("quote"):
            line += f"\n{'':<28}quote (page {item['page']}): {item['quote']}"
    return line


def _print_summary(summary: dict, failures: dict[str, str]) -> None:
    print()
    print("Legend: . correct  - correctly absent  M missed  W wrong  S spurious")
    print(f"Field order: {', '.join(FIELDS)}")
    print()
    print(f"Cases scored      {summary['cases']}  (failed calls: {len(failures)})")
    print(f"Field accuracy    {summary['field_accuracy']:.1%}")
    print(f"Recall            {summary['recall']:.1%}")
    print(f"Precision         {summary['precision']:.1%}")
    print(f"Unsafe values     {summary['unsafe_values']}")
    print(f"Verdict agreement {summary['verdict_agreement']:.1%}")
    verdicts = summary["verdicts"]
    print(
        f"Verdicts          {verdicts.get('match', 0)} match, "
        f"{verdicts.get('cautious', 0)} cautious, {verdicts.get('wrong', 0)} wrong"
    )
    print(f"Model calls/case  {summary['model_calls_per_case']:.2f}")
    print()
    header = f"{'field':<32}" + "".join(f"{o:>10}" for o in OUTCOMES)
    print(header)
    for name, counts in summary["per_field"].items():
        print(f"{name:<32}" + "".join(f"{counts.get(o, 0):>10}" for o in OUTCOMES))


def _save(model: str, summary: dict, scores: list[CaseScore], failures: dict) -> None:
    RESULTS.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = RESULTS / f"{stamp}_{model.replace('/', '_')}.json"
    payload = {
        "model": model,
        "summary": summary,
        "failures": failures,
        "cases": [
            {
                "id": s.case_id,
                "outcomes": s.outcomes,
                "expected_verdict": s.expected_verdict,
                "actual_verdict": s.actual_verdict,
                "rejected": s.rejected,
                "model_calls": s.model_calls,
                "details": s.details,
            }
            for s in scores
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved {path.relative_to(ROOT.parent)}")


if __name__ == "__main__":
    main()
