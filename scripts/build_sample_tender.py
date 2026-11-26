"""Rebuild tests/fixtures/sample_tender.pdf from scripts/sample_tender.html.

The fixture is a synthetic Arabic tender. It is exported with LibreOffice on purpose:
government tenders are usually exported from Word or LibreOffice, so the text layer
carries the same quirks a real document has.

Usage:
    python scripts/build_sample_tender.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "scripts" / "sample_tender.html"
TARGET = ROOT / "tests" / "fixtures" / "sample_tender.pdf"

CANDIDATES = (
    "soffice",
    "libreoffice",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
)


def find_soffice() -> str:
    for candidate in CANDIDATES:
        path = shutil.which(candidate) or (candidate if Path(candidate).exists() else None)
        if path:
            return path
    sys.exit("LibreOffice was not found. Install it: brew install --cask libreoffice")


def main() -> None:
    soffice = find_soffice()
    with tempfile.TemporaryDirectory() as out_dir:
        subprocess.run(
            [
                soffice,
                "--headless",
                "--convert-to",
                "pdf:writer_web_pdf_Export",
                str(SOURCE),
                "--outdir",
                out_dir,
            ],
            check=True,
            capture_output=True,
        )
        TARGET.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(Path(out_dir) / "sample_tender.pdf", TARGET)
    print(f"Wrote {TARGET.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
