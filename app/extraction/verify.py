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
from app.ingestion.text_quality import western_number

_NOT_WORD = re.compile(r"[^\w]+")
_ALEF = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ة": "ه", "ى": "ي"})
_PREFIXES = ("وال", "بال", "فال", "كال", "لل", "ال", "و", "ف", "ب", "ك", "ل")

MIN_QUOTE_WORDS = 2
_LONE_PREFIXES = {"و", "ف", "ب", "ك", "ل"}

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


_INDIC_NUMBER = re.compile(r"[٠-٩۰-۹](?:[٠-٩۰-۹٬٫,./]*[٠-٩۰-۹])?")


def compact(text: str) -> str:
    text = _INDIC_NUMBER.sub(lambda m: western_number(m.group()), text)
    text = text.translate(_ALEF).replace("\u0640", "")
    text = text.replace("لا", "ال")
    return _NOT_WORD.sub("", text)


def stem(word: str) -> str:
    word = compact(word)
    for prefix in _PREFIXES:
        if word.startswith(prefix) and len(word) - len(prefix) >= 2:
            return word[len(prefix) :]
    return word


def words(text: str) -> list[str]:
    tokens = [compact(t) for t in text.split()]
    merged: list[str] = []
    for token in tokens:
        if not token:
            continue
        # A prefix letter written apart (بـ الفئة) belongs to the next word.
        if merged and merged[-1] in _LONE_PREFIXES:
            merged[-1] += token
        else:
            merged.append(token)
    return [stem(t) for t in merged]


def quote_on_page(quote: str, page_text: str) -> bool:
    needle, page = words(quote), words(page_text)
    if not needle:
        return False
    if len(needle) < MIN_QUOTE_WORDS and not _distinctive(needle[0]):
        return False
    return any(_run_matches(needle, page, start) for start in range(len(page)))


def _distinctive(word: str) -> bool:
    """A lone number or date with enough digits is specific enough to cite on its own."""
    return sum(ch.isdigit() for ch in word) >= 4


def _run_matches(needle: list[str], page: list[str], start: int) -> bool:
    """Match quote words from page[start].

    PDF text layers sometimes split a word at a line break, or glue the first and
    last words of a quote to their neighbours, so one quote word may span two page
    words and the edge words may match the inner part of a page word.
    """
    i = start
    last = len(needle) - 1
    for n, word in enumerate(needle):
        if i >= len(page):
            return False
        token = page[i]
        glued_first = n == 0 and last > 0 and token.endswith(word)
        glued_last = n == last and last > 0 and token.startswith(word)
        if token == word or glued_first or glued_last:
            i += 1
        elif i + 1 < len(page) and stem(token + page[i + 1]) == word:
            i += 2
        else:
            return False
    return True


def number_in_quote(value: float | int, quote: str) -> bool:
    digits = re.sub(r"[^\d]", "", quote.replace(",", ""))
    number = str(int(value)) if float(value).is_integer() else str(value)
    return number in digits


def _plain(word: str) -> str:
    # Drops alef and lam so attached articles and the lam-alef ligature stop mattering.
    return compact(word).replace("ا", "").replace("ل", "")


def _forms(word: str) -> set[str]:
    # A quote word with and without one attached prefix; keywords are never stemmed,
    # since a word like كهروميكانيك starts with a letter that looks like a prefix.
    return {_plain(word), _plain(stem(word))}


# Words that show a requirement is stated. A requirement still missing after both readings
# while its words appear in the document is marked unverified instead of being ignored.
FIELD_MARKERS = {
    "work_category": ("مجال",),
    "required_classification_grade": ("الفئة",),
    "min_registered_capital": ("رأس المال",),
    "min_years_experience": ("خبرة",),
    "min_similar_projects": ("مماثل",),
    "submission_deadline": ("آخر موعد", "تاريخ الإغلاق", "موعد أقصاه"),
    "bid_guarantee_amount": ("كفالة دخول",),
}


def mentioned(field: str, text: str) -> bool:
    page = compact(text)
    return any(compact(marker) in page for marker in FIELD_MARKERS.get(field, ()))


def date_in_quote(value: str, quote: str) -> bool:
    """The ISO date value must be written in the quote, in any usual Arabic order."""
    try:
        year, month, day = (int(part) for part in str(value).split("-"))
    except ValueError:
        return False
    numbers = [int(n) for n in re.findall(r"\d+", compact_digits(quote))]
    for a, b, c in zip(numbers, numbers[1:], numbers[2:], strict=False):
        if (a, b, c) in ((year, month, day), (day, month, year)):
            return True
    return False


def compact_digits(text: str) -> str:
    return _INDIC_NUMBER.sub(lambda m: western_number(m.group()), text)


def grade_in_quote(grade: int, quote: str) -> bool:
    targets = {_plain(w) for w in GRADE_WORDS.get(grade, ())}
    return any(_forms(w) & targets for w in quote.split())


def category_in_quote(category: str, quote: str) -> bool:
    try:
        keywords = CATEGORY_WORDS.get(WorkCategory(category))
    except ValueError:
        return False
    if keywords is None:
        return True
    prefixes = [_plain(k) for k in keywords]
    return any(
        form.startswith(prefix) for w in quote.split() for form in _forms(w) for prefix in prefixes
    )
