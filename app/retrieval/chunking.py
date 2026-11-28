"""Splits a tender into short passages that keep their page number.

A passage holds one or two sentences and never crosses a page, so an answer built
on it cites one page and one requirement. Text is cut at sentence ends; a sentence
longer than `max_chars` is cut at a line end instead, and that line is repeated at
the start of the next passage.

Word and LibreOffice exports place the period of a right-to-left line at its start
(".مجال الأبنية"), so a line that starts with a period also ends a sentence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from pydantic import BaseModel

from app.ingestion.models import ExtractedDocument

MIN_CHARS = 120
MAX_CHARS = 300

# A period between digits is a decimal point, not a sentence end.
_SENTENCE_END = re.compile(r"(?<!\d)[.؟!؛?](?!\d)")
_LEADING_END = re.compile(r"^[.؟!؛?،,]+\s*")


class Chunk(BaseModel):
    page: int
    position: int
    text: str


@dataclass
class _Piece:
    text: str
    ends_sentence: bool


def chunk_document(
    document: ExtractedDocument,
    min_chars: int = MIN_CHARS,
    max_chars: int = MAX_CHARS,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    for page in document.pages:
        for text in _group(_pieces(page.text), min_chars, max_chars):
            chunks.append(Chunk(page=page.page_number, position=len(chunks), text=text))
    return chunks


def _pieces(text: str) -> list[_Piece]:
    pieces: list[_Piece] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        reversed_end = bool(_LEADING_END.match(line)) and line[0] in ".؟!؛?"
        line = _LEADING_END.sub("", line)
        parts = _SENTENCE_END.split(line)
        for i, part in enumerate(parts):
            part = part.strip()
            last = i == len(parts) - 1
            if part:
                pieces.append(_Piece(part, ends_sentence=not last or reversed_end))
            elif not last and pieces:
                pieces[-1].ends_sentence = True
    return pieces


def _group(pieces: list[_Piece], min_chars: int, max_chars: int) -> list[str]:
    passages: list[str] = []
    current: list[_Piece] = []

    def size(items: list[_Piece]) -> int:
        return len(" ".join(p.text for p in items))

    for piece in pieces:
        if current and size([*current, piece]) > max_chars:
            passages.append(" ".join(p.text for p in current))
            # Cut inside a sentence: repeat its last line so the sentence stays whole.
            carry = current[-1] if not current[-1].ends_sentence and len(current) > 1 else None
            current = [carry] if carry else []
        current.append(piece)
        if piece.ends_sentence and size(current) >= min_chars:
            passages.append(" ".join(p.text for p in current))
            current = []
    if current:
        passages.append(" ".join(p.text for p in current))
    return passages
