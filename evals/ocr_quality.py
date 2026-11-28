"""Measures how well each reading path recovers the text of the eval tenders.

No model is called. For every case the text is read twice: from the digital PDF's
text layer, and by OCR from the scanned copy. Each is compared with the true text:

- character accuracy: similarity of the normalized text to the source sentences
- key values: share of amounts and dates that appear intact

Usage:
    python -m evals.ocr_quality
    python -m evals.ocr_quality --dpi 300   (force a resolution instead of the scan's own)
"""

from __future__ import annotations

import argparse
import re
from difflib import SequenceMatcher
from pathlib import Path

from app.extraction.verify import compact
from app.ingestion import TesseractOcr, pdf_reader, read_pdf
from app.ingestion.text_quality import normalize_arabic
from evals.cases import CASES

PDFS = Path(__file__).resolve().parent / "pdfs"
KEY_FIELDS = ("min_registered_capital", "min_similar_project_value", "bid_guarantee_amount")


def reference_text(case: dict) -> str:
    return "\n".join(normalize_arabic("\n".join(lines)) for lines in case["pages"])


def key_values(case: dict) -> list[str]:
    values = [str(case["expected"][f]) for f in KEY_FIELDS if case["expected"][f] is not None]
    deadline = case["expected"]["submission_deadline"]
    if deadline:
        year, month, day = deadline.split("-")
        values.append(f"{year}{month}{day}")
    return values


def character_accuracy(text: str, reference: str) -> float:
    return SequenceMatcher(None, compact(text), compact(reference), autojunk=False).ratio()


def values_found(text: str, values: list[str]) -> int:
    digits = re.sub(r"[^\d]", "", text)
    return sum(1 for value in values if value in digits)


def measure(path: Path, case: dict, ocr: TesseractOcr | None) -> tuple[float, int, int]:
    document = read_pdf(path.read_bytes(), ocr=ocr)
    text = "\n".join(page.text for page in document.pages)
    values = key_values(case)
    return character_accuracy(text, reference_text(case)), values_found(text, values), len(values)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dpi", type=int, default=None)
    args = parser.parse_args()
    if args.dpi:
        pdf_reader.MIN_SCAN_DPI = pdf_reader.MAX_SCAN_DPI = args.dpi

    if not TesseractOcr.available():
        raise SystemExit("Tesseract is not installed.")
    ocr = TesseractOcr()

    print(f"{'case':<24}{'text layer':>12}{'ocr':>10}{'values (layer)':>17}{'values (ocr)':>15}")
    totals = {"layer": [], "ocr": [], "layer_found": 0, "ocr_found": 0, "values": 0}
    for case in CASES:
        name = f"{case['id']}.pdf"
        layer_acc, layer_found, count = measure(PDFS / name, case, None)
        ocr_acc, ocr_found, _ = measure(PDFS / "scanned" / name, case, ocr)
        totals["layer"].append(layer_acc)
        totals["ocr"].append(ocr_acc)
        totals["layer_found"] += layer_found
        totals["ocr_found"] += ocr_found
        totals["values"] += count
        print(
            f"{case['id']:<24}{layer_acc:>12.1%}{ocr_acc:>10.1%}"
            f"{f'{layer_found}/{count}':>17}{f'{ocr_found}/{count}':>15}"
        )

    layer_mean = sum(totals["layer"]) / len(totals["layer"])
    ocr_mean = sum(totals["ocr"]) / len(totals["ocr"])
    print()
    print(f"OCR at {args.dpi or 'native'} dpi")
    print(f"Character accuracy  text layer {layer_mean:.1%}   OCR {ocr_mean:.1%}")
    print(
        f"Key values intact   text layer {totals['layer_found']}/{totals['values']}   "
        f"OCR {totals['ocr_found']}/{totals['values']}"
    )


if __name__ == "__main__":
    main()
