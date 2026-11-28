"""Tools the agent can call, bound to one processed tender.

Each tool returns JSON text for the model and a short summary for the trace. The
qualification verdict comes from the rule engine's report, stored when the job ran.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from app.agent.models import TenderContext
from app.qa import AnswerStatus, Citation, TenderQA

SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "ask_tender",
            "description": "Answers one question from the tender text, with quotes and pages.",
            "parameters": {
                "type": "object",
                "properties": {"question": {"type": "string", "description": "Arabic question"}},
                "required": ["question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_requirements",
            "description": "Requirements extracted from the tender, and those not verified.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_qualification",
            "description": "The company's qualification verdict and gaps from the rule engine.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


@dataclass
class ToolResult:
    content: str
    summary: str
    citations: list[Citation] = field(default_factory=list)
    report: dict[str, Any] | None = None


class TenderTools:
    def __init__(self, qa: TenderQA, context: TenderContext) -> None:
        self.qa = qa
        self.context = context

    def run(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        if name == "ask_tender":
            return self._ask(str(arguments.get("question", "")))
        if name == "get_requirements":
            return self._requirements()
        if name == "check_qualification":
            return self._qualification()
        return ToolResult(_json({"error": f"unknown tool {name}"}), f"unknown tool {name}")

    def _ask(self, question: str) -> ToolResult:
        if not question.strip():
            return ToolResult(_json({"error": "empty question"}), "empty question")
        answer = self.qa.ask(self.context.document_id, question)
        if answer.status is not AnswerStatus.ANSWERED:
            # Unsupported answers are not passed on, so the model cannot repeat them.
            return ToolResult(_json({"status": "not_found"}), f"{question} -> not found")
        content = {
            "status": "answered",
            "answer": answer.answer,
            "citations": [c.model_dump() for c in answer.citations],
        }
        pages = ", ".join(str(c.page) for c in answer.citations)
        return ToolResult(_json(content), f"{question} -> page {pages}", answer.citations)

    def _requirements(self) -> ToolResult:
        return ToolResult(_json(self.context.requirements), "read extracted requirements")

    def _qualification(self) -> ToolResult:
        report = self.context.report
        if report is None:
            content = {"error": "no company profile was sent with this tender"}
            return ToolResult(_json(content), "no company profile")
        return ToolResult(_json(report), f"verdict {report.get('verdict')}", report=report)


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)
