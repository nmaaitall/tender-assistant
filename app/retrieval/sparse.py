"""Lexical vectors for Arabic text.

Words are normalized the same way citations are checked (alef forms, taa marbuta,
the reversed lam-alef ligature), then the article and a common suffix are removed,
so كفالة and بالكفالة, or مماثلة and مماثلين, count as the same term. Each term is
hashed to a vector index; Qdrant applies IDF at search time.
"""

from __future__ import annotations

import math
import zlib
from collections import Counter

from app.extraction.verify import compact

_STOPWORD_TEXT = (
    "في من على عن إلى الى أن ان أو او ما هو هي هذا هذه ذلك التي الذي كل لا مع قد "
    "كان يكون يجب هل كم متى أي اي"
)
_STOPWORDS = {compact(w) for w in _STOPWORD_TEXT.split()}
_ARTICLES = ("وال", "بال", "فال", "كال", "لل", "ال")
_LETTER_PREFIXES = "وفبكل"
_SUFFIXES = ("ات", "ين", "ون", "ان", "يه", "ه", "ي")
_MIN_STEM = 3


def light_stem(word: str) -> str:
    for suffix in _SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= _MIN_STEM:
            return word[: -len(suffix)]
    return word


def _forms(token: str) -> list[str]:
    # The article before an alef reads اال after normalization (الأبنية -> االبنيه).
    if token.startswith("اال") and len(token) > 4:
        return ["ا" + token[3:]]
    for article in _ARTICLES:
        if token.startswith(article) and len(token) - len(article) >= 2:
            return [token[len(article) :]]
    # A single letter may be a prefix (بكفالة) or part of the word (كفالة), so both
    # readings are kept.
    if token[0] in _LETTER_PREFIXES and len(token) >= 4:
        return [token, token[1:]]
    return [token]


def terms(text: str) -> list[str]:
    found: list[str] = []
    for raw in text.split():
        token = compact(raw)
        if len(token) < 2 or token in _STOPWORDS:
            continue
        found.extend(light_stem(form) for form in _forms(token))
    return found


def sparse_vector(text: str, query: bool = False) -> tuple[list[int], list[float]]:
    counts = Counter(_index(term) for term in terms(text))
    indices = sorted(counts)
    if query:
        return indices, [1.0] * len(indices)
    # Repeats count, but less than linearly. Passage length is not penalized, since a
    # tender often states several requirements in one paragraph.
    return indices, [1.0 + math.log(counts[i]) for i in indices]


def _index(term: str) -> int:
    return zlib.crc32(term.encode("utf-8")) & 0x7FFFFFFF
