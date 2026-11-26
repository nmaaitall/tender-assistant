"""Arabic text normalization and text-layer quality checks.

PDFs exported from Word or LibreOffice often carry a text layer that is close to
correct. Others carry a broken one: wrong ToUnicode maps produce characters from
unrelated scripts. Those pages are treated like scans and sent to OCR.
"""

from __future__ import annotations

import re
import unicodedata

# Characters that legitimately appear in an Arabic tender document.
_ALLOWED_RANGES = (
    (0x0020, 0x007E),  # basic Latin, digits, punctuation
    (0x00A0, 0x00FF),  # Latin-1 punctuation and symbols
    (0x0600, 0x06FF),  # Arabic
    (0x0750, 0x077F),  # Arabic supplement
    (0x2000, 0x206F),  # general punctuation
    (0x20A0, 0x20CF),  # currency symbols
)

_TASHKEEL = re.compile(r"\s*[ً-ْٰ]")
_TATWEEL = "ـ"
_BIDI_CONTROLS = re.compile(r"[​-‏‪-‮⁦-⁩﻿]")
_ARABIC_THEN_LATIN = re.compile(r"([؀-ۿ])([0-9A-Za-z])")
_LATIN_THEN_ARABIC = re.compile(r"([0-9A-Za-z])([؀-ۿ])")
_SPACES = re.compile(r"[ \t ]+")
_BLANK_LINES = re.compile(r"\n\s*\n+")

_INDIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹٬٫", "01234567890123456789,.")
_INDIC_NUMBER = re.compile(r"[٠-٩۰-۹](?:[٠-٩۰-۹٬٫,./]*[٠-٩۰-۹])?")
_THOUSANDS = re.compile(r"[1-9]\d{0,2}(,\d{3})*(\.\d+)?|0(\.\d+)?")
_DATE = re.compile(r"(19|20)\d{2}/\d{1,2}/\d{1,2}|\d{1,2}/\d{1,2}/(19|20)\d{2}")

MIN_MEANINGFUL_CHARS = 30
MAX_GARBLED_RATIO = 0.15


def normalize_arabic(text: str) -> str:
    """Make extracted Arabic text consistent for search and for the model."""
    text = unicodedata.normalize("NFKC", text)  # presentation forms -> base letters
    text = _INDIC_NUMBER.sub(lambda m: western_number(m.group()), text)
    text = _BIDI_CONTROLS.sub("", text)
    text = text.replace(_TATWEEL, "")
    text = _TASHKEEL.sub("", text)
    text = _ARABIC_THEN_LATIN.sub(r"\1 \2", text)
    text = _LATIN_THEN_ARABIC.sub(r"\1 \2", text)
    lines = [_SPACES.sub(" ", line).strip() for line in text.splitlines()]
    text = "\n".join(line for line in lines if line and not _is_punctuation_only(line))
    return _BLANK_LINES.sub("\n", text).strip()


def western_number(number: str) -> str:
    """Converts an Arabic-Indic number to ASCII digits.

    Some PDF producers store Arabic-Indic numbers in reverse character order
    (120,000 is extracted as 000,021). The reversed reading is used only when it is a
    well-formed amount or date and the original is not.
    """
    as_is = number.translate(_INDIC_DIGITS)
    reversed_ = as_is[::-1]
    if not _well_formed(as_is) and _well_formed(reversed_):
        return reversed_
    return as_is


def _well_formed(number: str) -> bool:
    if "/" in number:
        return bool(_DATE.fullmatch(number))
    if "," in number or "." in number:
        return bool(_THOUSANDS.fullmatch(number))
    return not (len(number) > 1 and number.startswith("0"))


def meaningful_char_count(text: str) -> int:
    return sum(1 for ch in text if not ch.isspace())


def garbled_ratio(text: str) -> float:
    """Share of visible characters that do not belong in an Arabic or Latin document."""
    visible = [ch for ch in text if not ch.isspace()]
    if not visible:
        return 0.0
    bad = sum(1 for ch in visible if not _is_allowed(ch))
    return round(bad / len(visible), 4)


def is_usable(text: str) -> bool:
    return (
        meaningful_char_count(text) >= MIN_MEANINGFUL_CHARS
        and garbled_ratio(text) <= MAX_GARBLED_RATIO
    )


def _is_allowed(ch: str) -> bool:
    code = ord(ch)
    return any(low <= code <= high for low, high in _ALLOWED_RANGES)


def _is_punctuation_only(line: str) -> bool:
    return all(unicodedata.category(ch).startswith(("P", "Z")) for ch in line)
