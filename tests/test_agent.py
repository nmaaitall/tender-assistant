import json

from qdrant_client import QdrantClient

from app.agent import TenderAgent, TenderContext
from app.ingestion import ExtractedDocument, PageSource, PageText
from app.qa import TenderQA
from app.retrieval import ChunkIndex, chunk_document
from tests.fake_llm import FakeLLM

PAGES = [
    "آخر موعد لتقديم العروض يوم 2026/10/15",
    "يقدم المقاول مع عرضه كفالة دخول عطاء بقيمة 20,000 دينار أردني.",
]
REPORT = {"verdict": "not_qualified", "gaps": [{"rule": "registered_capital"}]}


class ScriptedChat:
    """Plays back assistant messages in order and records what it was sent."""

    def __init__(self, messages):
        self.messages = list(messages)
        self.sent = []

    def chat(self, messages, tools):
        self.sent.append(list(messages))
        return self.messages.pop(0) if self.messages else _call("check_qualification")


def _call(name, call_id="c1", **arguments):
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(arguments, ensure_ascii=False)},
            }
        ],
    }


def _final(text):
    return {"role": "assistant", "content": text}


def _agent(chat, qa_response=None, report=REPORT):
    document = ExtractedDocument(
        filename="t.pdf",
        page_count=len(PAGES),
        pages=[
            PageText(page_number=i, source=PageSource.TEXT_LAYER, text=text)
            for i, text in enumerate(PAGES, start=1)
        ],
    )
    index = ChunkIndex(QdrantClient(":memory:"))
    index.add("t", chunk_document(document))
    qa = TenderQA(FakeLLM(qa_response or {"answer": None, "citations": []}), index)
    context = TenderContext(
        document_id="t", requirements={"min_registered_capital": 100000}, report=report
    )
    return TenderAgent(chat, qa), context


GUARANTEE = {
    "answer": "قيمة كفالة دخول العطاء 20,000 دينار أردني.",
    "citations": [{"page": 2, "quote": "كفالة دخول عطاء بقيمة 20,000 دينار أردني"}],
}


def test_agent_uses_tools_then_answers():
    chat = ScriptedChat(
        [
            _call("check_qualification"),
            _call("ask_tender", call_id="c2", question="ما قيمة كفالة دخول العطاء؟"),
            _final("الشركة غير مؤهلة بسبب رأس المال، وكفالة الدخول 20,000 دينار (صفحة 2)."),
        ]
    )
    agent, context = _agent(chat, GUARANTEE)
    result = agent.run(context, "هل نحن مؤهلون؟ وكم الكفالة؟")

    assert [s.tool for s in result.steps] == ["check_qualification", "ask_tender"]
    assert result.report == REPORT
    assert result.citations[0].page == 2
    assert result.model_calls == 3
    assert result.unsupported_numbers == []
    assert result.stopped is None
    # The tool result goes back to the model as a tool message.
    assert chat.sent[1][-1]["role"] == "tool"


def test_amount_no_tool_returned_is_flagged():
    chat = ScriptedChat([_call("get_requirements"), _final("رأس المال المطلوب 250,000 دينار.")])
    agent, context = _agent(chat)
    result = agent.run(context, "كم رأس المال المطلوب؟")
    assert result.unsupported_numbers == ["250000"]


def test_not_found_answer_is_passed_on_without_text():
    chat = ScriptedChat(
        [_call("ask_tender", question="ما ثمن نسخة الكراسة؟"), _final("غير مذكور في الكراسة.")]
    )
    agent, context = _agent(chat)
    result = agent.run(context, "ما ثمن نسخة الكراسة؟")
    tool_message = chat.sent[1][-1]
    assert json.loads(tool_message["content"]) == {"status": "not_found"}
    assert result.citations == []


def test_qualification_without_a_profile():
    chat = ScriptedChat([_call("check_qualification"), _final("لم يرسل ملف الشركة.")])
    agent, context = _agent(chat, report=None)
    result = agent.run(context, "هل نحن مؤهلون؟")
    assert result.report is None
    assert result.steps[0].summary == "no company profile"


def test_agent_stops_after_the_call_limit():
    chat = ScriptedChat([])  # asks for a tool every time
    agent, context = _agent(chat)
    agent.max_calls = 3
    result = agent.run(context, "سؤال")
    assert result.model_calls == 3
    assert result.answer is None
    assert result.stopped == "stopped after 3 model calls"
