"""Build evals/pdfs/*.pdf from the cases in evals/cases.py.

Usage:
    python scripts/build_eval_set.py
"""

from __future__ import annotations

import html
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evals.cases import CASES  # noqa: E402
from scripts.build_sample_tender import find_soffice  # noqa: E402

OUT = ROOT / "evals" / "pdfs"

PAGE_STYLE = """
body { font-family: "DejaVu Sans"; font-size: 13pt; }
.page { page-break-before: always; }
"""


def to_html(pages: list[list[str]]) -> str:
    parts = []
    for number, lines in enumerate(pages):
        for index, line in enumerate(lines):
            # LibreOffice honours page breaks on paragraphs, not on wrapping divs.
            css_class = ' class="page"' if number and index == 0 else ""
            parts.append(f"<p{css_class}>{html.escape(line)}</p>")
    return (
        '<!DOCTYPE html><html dir="rtl" lang="ar"><head><meta charset="utf-8">'
        f"<style>{PAGE_STYLE}</style></head><body>{''.join(parts)}</body></html>"
    )


def main() -> None:
    soffice = find_soffice()
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        sources = []
        for item in CASES:
            source = Path(tmp) / f"{item['id']}.html"
            source.write_text(to_html(item["pages"]), encoding="utf-8")
            sources.append(str(source))
        subprocess.run(
            [soffice, "--headless", "--convert-to", "pdf:writer_web_pdf_Export", "--outdir", tmp]
            + sources,
            check=True,
            capture_output=True,
        )
        for item in CASES:
            shutil.copy(Path(tmp) / f"{item['id']}.pdf", OUT / f"{item['id']}.pdf")
    print(f"Wrote {len(CASES)} PDFs to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
