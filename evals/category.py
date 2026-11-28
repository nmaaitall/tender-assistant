"""Checks the trained category classifier on the eval tenders.

The classifier was trained on synthetic titles and scopes only, so these tenders
are text it has not seen in that form. The first page of each digital PDF is
classified, as the job does.

    python -m evals.category
"""

from __future__ import annotations

from pathlib import Path

from app.classify import CategoryClassifier
from app.ingestion import read_pdf
from app.jobs.tasks import FLAG_CONFIDENCE
from evals.cases import CASES

PDFS = Path(__file__).resolve().parent / "pdfs"


def main() -> None:
    classifier = CategoryClassifier()
    correct = confident = confident_correct = 0
    for case in CASES:
        document = read_pdf((PDFS / f"{case['id']}.pdf").read_bytes(), case["id"])
        prediction = classifier.predict(document.pages[0].text)
        expected = case["expected"]["work_category"]
        ok = prediction.category == expected
        correct += ok
        if prediction.confidence >= FLAG_CONFIDENCE:
            confident += 1
            confident_correct += ok
        mark = "ok " if ok else "BAD"
        name, conf = case["id"], prediction.confidence
        print(f"{name:<24} {mark} {expected:<20} {prediction.category:<20} {conf:.2f}")

    print(f"\nAccuracy                 {correct}/{len(CASES)}")
    print(f"Confidence >= {FLAG_CONFIDENCE}        {confident_correct}/{confident} correct")
    print("Wrong and confident ones would be flagged against the extracted category.")


if __name__ == "__main__":
    main()
