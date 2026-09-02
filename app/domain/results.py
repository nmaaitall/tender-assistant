from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from app.domain.enums import RuleStatus, Verdict


class RuleResult(BaseModel):
    rule_id: str
    status: RuleStatus
    message: str
    required: str | None = None
    actual: str | None = None
    remediable: bool = False


class Gap(BaseModel):
    rule_id: str
    message: str
    remediable: bool


class QualificationReport(BaseModel):
    tender_reference: str
    company_name: str
    verdict: Verdict
    headline: str
    evaluated_at: date
    results: list[RuleResult] = Field(default_factory=list)
    gaps: list[Gap] = Field(default_factory=list)
