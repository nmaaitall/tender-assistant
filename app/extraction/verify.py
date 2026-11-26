"""Checks that a model citation really exists on the page it points to, and that the
value agrees with its quote.

Quotes are compared word by word. Each word is normalized (alef forms, taa marbuta,
the reversed lam-alef ligature of Word and LibreOffice exports) and stripped of one
attached prefix (و ف ب ك ل ال لل). The quote's words must appear as one continuous
run on the page, so a changed or invented word fails the check.
"""

from __future__ import annotations

import re

from app.domain.enums import WorkCategory

_NOT_WORD = re.compile(r"[^\w]+")
_ALEF = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ة": "ه", "ى": "ي"})
_PREFIXES = ("وال", "بال", "فال", "كال", "لل", "ال", "و", "ف", "ب", "ك", "ل")

MIN_QUOTE_WORDS = 2

GRADE_WORDS = {
    1: ("الاولي", "1"),
    2: ("الثانيه", "2"),
    3: ("الثالثه", "3"),
    4: ("الرابعه", "4"),
    5: ("الخامسه", "5"),
    6: ("السادسه", "6"),
}

CATEGORY_WORDS = {
    WorkCategory.BUILDINGS: ("ابنيه", "مباني", "مبني"),
    WorkCategory.ROADS: ("طرق",),
    WorkCategory.ELECTROMECHANICAL: ("كهروميكانيك",),
    WorkCategory.WATER_AND_SEWERAGE: ("مياه", "صرف"),
}


def compact(text: str) -> str:
    text = text.translate(_ALEF)
    text = text.replace("لا", "ال")
    return _NOT_WORD.sub("", text)


def stem(word: str) -> str:
    word = compact(word)
    for prefix in _PREFIXES:
        if word.startswith(prefix) and len(word) - len(prefix) >= 2:
            return word[len(prefix) :]
    return word


def words(text: str) -> list[str]:
    return [s for s in (stem(w) for w in text.split()) if s]


def quote_on_page(quote: str, page_text: str) -> bool:
    needle, page = words(quote), words(page_text)
    if len(needle) < MIN_QUOTE_WORDS:
        return False
    return any(_run_matches(needle, page, start) for start in range(len(page)))


def _run_matches(needle: list[str], page: list[str], start: int) -> bool:
    """Match quote words from page[start], letting one quote word span two page words.

    PDF text layers sometimes split a word at a line break or a shaping boundary.
    """
    i = start
    for word in needle:
        if i < len(page) and page[i] == word:
            i += 1
        elif i + 1 < len(page) and stem(page[i] + page[i + 1]) == word:
            i += 2
        else:
            return False
    return True


def number_in_quote(value: float | int, quote: str) -> bool:
    digits = re.sub(r"[^\d]", "", quote.replace(",", ""))
    number = str(int(value)) if float(value).is_integer() else str(value)
    return number in digits


def _loose(word: str) -> str:
    # Drops alef and lam so attached articles and the lam-alef ligature stop mattering.
    return compact(word).replace("ا", "").replace("ل", "")


def grade_in_quote(grade: int, quote: str) -> bool:
    targets = {_loose(w) for w in GRADE_WORDS.get(grade, ())}
    return any(_loose(w) in targets for w in quote.split())


def category_in_quote(category: str, quote: str) -> bool:
    try:
        keywords = CATEGORY_WORDS.get(WorkCategory(category))
    except ValueError:
        return False
    if keywords is None:
        return True
    prefixes = [_loose(k) for k in keywords]
    return any(_loose(w).startswith(p) for w in quote.split() for p in prefixes)
