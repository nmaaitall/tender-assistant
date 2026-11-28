"""Arabic OCR for scanned pages, using the Tesseract command line tool.

Install Tesseract with Arabic data:
    macOS:  brew install tesseract tesseract-lang
    Debian: apt-get install tesseract-ocr tesseract-ocr-ara
"""

from __future__ import annotations

import shutil
import subprocess
from typing import Protocol


class OcrError(RuntimeError):
    """OCR could not run on a page."""


class OcrEngine(Protocol):
    def recognize(self, image_png: bytes) -> str: ...


class TesseractOcr:
    def __init__(
        self,
        languages: str = "ara+eng",
        page_segmentation: int = 4,
        timeout: float = 60.0,
        binary: str = "tesseract",
    ) -> None:
        self.languages = languages
        self.page_segmentation = page_segmentation
        self.timeout = timeout
        self.binary = binary

    @classmethod
    def available(cls, binary: str = "tesseract") -> bool:
        return shutil.which(binary) is not None

    def recognize(self, image_png: bytes) -> str:
        command = [
            self.binary,
            "stdin",
            "stdout",
            "-l",
            self.languages,
            "--psm",
            str(self.page_segmentation),
        ]
        try:
            completed = subprocess.run(
                command, input=image_png, capture_output=True, timeout=self.timeout, check=True
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise OcrError(f"Tesseract failed: {exc}") from exc
        return completed.stdout.decode("utf-8", errors="replace")
