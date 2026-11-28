from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.qa import Citation


class TenderContext(BaseModel):
    """What the agent may use about one processed tender."""

    document_id: str
    requirements: dict[str, Any]
    report: dict[str, Any] | None = None


class AgentStep(BaseModel):
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    summary: str


class AgentAnswer(BaseModel):
    """The verdict, when present, is the rule engine's report, never the model's opinion.
    Amounts in the answer that no tool returned are listed in unsupported_numbers."""

    question: str
    answer: str | None
    citations: list[Citation] = Field(default_factory=list)
    report: dict[str, Any] | None = None
    steps: list[AgentStep] = Field(default_factory=list)
    model_calls: int = 0
    unsupported_numbers: list[str] = Field(default_factory=list)
    stopped: str | None = None
