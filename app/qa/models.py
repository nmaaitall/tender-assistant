from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class AnswerStatus(StrEnum):
    ANSWERED = "answered"
    NOT_FOUND = "not_found"
    UNSUPPORTED = "unsupported"


class Citation(BaseModel):
    page: int
    quote: str


class Answer(BaseModel):
    """An answer is only returned when every citation was found in the passages read
    and every number in it appears in a citation."""

    question: str
    status: AnswerStatus
    answer: str | None = None
    citations: list[Citation] = Field(default_factory=list)
    pages_read: list[int] = Field(default_factory=list)
    reason: str | None = None
