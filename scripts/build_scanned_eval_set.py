"""Build evals/pdfs/scanned/*.pdf: image-only copies of the eval PDFs with scan damage.

Each page is rendered at a low resolution, tilted slightly, blurred, sprinkled with
speckle noise and saved as a compressed JPEG, so the text layer is gone and OCR
has to read it the way it would read a real scan. The damage is seeded per case.

Usage:
    python scripts/build_scanned_eval_set.py
"""

from __future__ import annotations

import io
import random
import sys
from pathlib import Path

import pymupdf
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evals.cases import CASES  # noqa: E402

SOURCE = ROOT / "evals" / "pdfs"
OUT = SOURCE / "scanned"

SCAN_DPI = 150
JPEG_QUALITY = 55
SPECKLE_RATIO = 0.004


def damage(image: Image.Image, rng: random.Random) -> Image.Image:
    image = image.rotate(rng.uniform(-1.2, 1.2), fillcolor=255, resample=Image.BICUBIC)
    image = image.filter(ImageFilter.GaussianBlur(radius=rng.uniform(0.3, 0.7)))
    pixels = image.load()
    width, height = image.size
    for _ in range(int(width * height * SPECKLE_RATIO)):
        x, y = rng.randrange(width), rng.randrange(height)
        pixels[x, y] = 0 if rng.random() < 0.5 else 255
    return image


def scan(source: Path, target: Path, seed: str) -> None:
    rng = random.Random(seed)
    original = pymupdf.open(source)
    scanned = pymupdf.open()
    for page in original:
        pixmap = page.get_pixmap(dpi=SCAN_DPI, colorspace=pymupdf.csGRAY)
        image = Image.open(io.BytesIO(pixmap.tobytes("png"))).convert("L")
        buffer = io.BytesIO()
        damage(image, rng).save(buffer, format="JPEG", quality=JPEG_QUALITY)
        new_page = scanned.new_page(width=page.rect.width, height=page.rect.height)
        new_page.insert_image(new_page.rect, stream=buffer.getvalue())
    scanned.save(target, garbage=4, deflate=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for item in CASES:
        scan(SOURCE / f"{item['id']}.pdf", OUT / f"{item['id']}.pdf", seed=item["id"])
    print(f"Wrote {len(CASES)} scanned PDFs to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
