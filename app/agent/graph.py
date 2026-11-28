"""A tool-using agent over one processed tender, built as a LangGraph state graph.

    agent --(tool calls)--> tools --> agent --(no tool calls)--> end

The model decides which tools to call and in what order; the graph runs them and
feeds the results back. Guards:

- at most MAX_MODEL_CALLS model calls per question
- the verdict is taken from the rule engine's report, not from the model's text
- amounts in the final answer that no tool returned are flagged
"""

from __future__ import annotations

import json
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from app.agent.models import AgentAnswer, AgentStep, TenderContext
from app.agent.prompt import SYSTEM_PROMPT
from app.agent.tools import SCHEMAS, TenderTools
from app.extraction.llm import ChatClient
from app.qa import Citation, TenderQA
from app.qa.answerer import MIN_CHECKED_NUMBER, numbers_in

MAX_MODEL_CALLS = 6


class AgentState(TypedDict):
    messages: list[dict[str, Any]]
    steps: list[AgentStep]
    citations: list[Citation]
    report: dict[str, Any] | None
    tool_text: str
    calls: int


class TenderAgent:
    def __init__(self, llm: ChatClient, qa: TenderQA, max_calls: int = MAX_MODEL_CALLS) -> None:
        self.llm = llm
        self.qa = qa
        self.max_calls = max_calls

    def run(self, context: TenderContext, question: str) -> AgentAnswer:
        graph = self._build(TenderTools(self.qa, context))
        state: AgentState = {
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": question},
            ],
            "steps": [],
            "citations": [],
            "report": None,
            "tool_text": "",
            "calls": 0,
        }
        final = graph.invoke(state, {"recursion_limit": 2 * self.max_calls + 4})

        last = final["messages"][-1]
        stopped = None
        answer = None
        if last.get("tool_calls"):
            stopped = f"stopped after {self.max_calls} model calls"
        else:
            answer = (last.get("content") or "").strip() or None

        return AgentAnswer(
            question=question,
            answer=answer,
            citations=_unique(final["citations"]),
            report=final["report"],
            steps=final["steps"],
            model_calls=final["calls"],
            unsupported_numbers=_unsupported(answer or "", final["tool_text"]),
            stopped=stopped,
        )

    def _build(self, tools: TenderTools):
        def agent(state: AgentState) -> dict[str, Any]:
            message = self.llm.chat(state["messages"], SCHEMAS)
            return {
                "messages": [*state["messages"], _assistant(message)],
                "calls": state["calls"] + 1,
            }

        def run_tools(state: AgentState) -> dict[str, Any]:
            messages = list(state["messages"])
            steps = list(state["steps"])
            citations = list(state["citations"])
            report = state["report"]
            tool_text = state["tool_text"]
            for call in messages[-1]["tool_calls"]:
                name = call["function"]["name"]
                arguments = _arguments(call["function"].get("arguments"))
                result = tools.run(name, arguments)
                messages.append(
                    {"role": "tool", "tool_call_id": call["id"], "content": result.content}
                )
                steps.append(AgentStep(tool=name, arguments=arguments, summary=result.summary))
                citations += result.citations
                report = result.report or report
                tool_text += " " + result.content
            return {
                "messages": messages,
                "steps": steps,
                "citations": citations,
                "report": report,
                "tool_text": tool_text,
            }

        def next_step(state: AgentState) -> str:
            wants_tools = bool(state["messages"][-1].get("tool_calls"))
            return "tools" if wants_tools and state["calls"] < self.max_calls else END

        graph = StateGraph(AgentState)
        graph.add_node("agent", agent)
        graph.add_node("tools", run_tools)
        graph.set_entry_point("agent")
        graph.add_conditional_edges("agent", next_step, {"tools": "tools", END: END})
        graph.add_edge("tools", "agent")
        return graph.compile()


def _assistant(message: dict[str, Any]) -> dict[str, Any]:
    # Only the fields the chat API accepts back; reasoning text is dropped.
    kept: dict[str, Any] = {"role": "assistant", "content": message.get("content") or ""}
    if message.get("tool_calls"):
        kept["tool_calls"] = message["tool_calls"]
    return kept


def _arguments(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _unique(citations: list[Citation]) -> list[Citation]:
    seen: set[tuple[int, str]] = set()
    unique = []
    for c in citations:
        if (c.page, c.quote) not in seen:
            seen.add((c.page, c.quote))
            unique.append(c)
    return unique


def _unsupported(answer: str, tool_text: str) -> list[str]:
    returned = numbers_in(tool_text)
    return sorted(
        n for n in numbers_in(answer) if int(n) >= MIN_CHECKED_NUMBER and n not in returned
    )
