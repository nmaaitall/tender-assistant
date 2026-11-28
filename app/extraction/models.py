from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.tender import TenderRequirements


class Citation(BaseModel):
    """Where a value was found: the page number and the sentence it came from."""

    page: int = Field(ge=1)
    quote: str


class RequiredDocument(BaseModel):
    name: str
    citation: Citation


class RejectedField(BaseModel):
    field: str
    reason: str
    page: int | None = None
    quote: str | None = None


class ExtractionResult(BaseModel):
    requirements: TenderRequirements
    citations: dict[str, Citation] = Field(default_factory=dict)
    required_documents: list[RequiredDocument] = Field(default_factory=list)
    rejected: list[RejectedField] = Field(default_factory=list)
    model: str
    model_calls: int = 1
