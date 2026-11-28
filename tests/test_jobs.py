import json
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from app import db
from app.agent import TenderAgent
from app.api.dependencies import get_agent, get_qa
from app.extraction import ExtractionNotConfigured, LLMError, TenderExtractor
from app.jobs import tasks
from app.jobs.models import Job, JobStatus
from app.main import app
from app.qa import TenderQA
from app.retrieval import ChunkIndex
from app.worker import celery_app
from tests.fake_llm import SAMPLE_RESPONSE, FakeLLM

SAMPLE = Path(__file__).parent / "fixtures" / "sample_tender.pdf"


INDEX = ChunkIndex(QdrantClient(":memory:"))


@pytest.fixture(autouse=True)
def database(tmp_path, monkeypatch):
    engine = db.configure(f"sqlite:///{tmp_path / 'jobs.db'}")
    db.Base.metadata.create_all(engine)
    monkeypatch.setattr(tasks, "get_ocr", lambda: None)
    # Lexical search in memory: no model download and no Qdrant server in tests.
    monkeypatch.setattr(tasks, "get_index", lambda: INDEX)
    # Celery's lazy config object cannot be restored by monkeypatch, so set it directly.
    eager = celery_app.conf.task_always_eager
    celery_app.conf.task_always_eager = True
    yield
    celery_app.conf.task_always_eager = eager
    engine.dispose()


@pytest.fixture
def fake_model(monkeypatch):
    extractor = TenderExtractor(FakeLLM(SAMPLE_RESPONSE), model_name="fake")
    monkeypatch.setattr(tasks, "create_extractor", lambda: extractor)


client = TestClient(app)


def _submit(profile=None, pdf: bytes | None = None, as_of="2026-09-02"):
    data = {"as_of": as_of}
    if profile is not None:
        data["profile"] = profile if isinstance(profile, str) else profile.model_dump_json()
    return client.post(
        "/api/v1/jobs",
        files={"file": ("sample_tender.pdf", pdf or SAMPLE.read_bytes(), "application/pdf")},
        data=data,
    )


def test_job_runs_to_a_verdict(fake_model, profile):
    response = _submit(profile)
    assert response.status_code == 202
    body = response.json()
    assert response.headers["Location"] == body["status_url"]

    job = client.get(body["status_url"]).json()
    assert job["status"] == "succeeded"
    assert job["page_count"] == 4
    assert job["pages_done"] == 4
    assert job["result"]["document"]["kind"] == "digital"
    assert job["result"]["extraction"]["requirements"]["reference"] == "ZM-2026-014"
    assert job["result"]["report"]["verdict"] == "qualified"
    assert job["started_at"] and job["finished_at"]


def test_job_without_profile_has_no_report(fake_model):
    job = client.get(_submit().json()["status_url"]).json()
    assert job["status"] == "succeeded"
    assert job["result"]["report"] is None


def test_model_failure_fails_the_job(monkeypatch):
    class Broken:
        def extract(self, document):
            raise LLMError("Model call failed: 429")

    monkeypatch.setattr(tasks, "create_extractor", lambda: Broken())
    job = client.get(_submit().json()["status_url"]).json()
    assert job["status"] == "failed"
    assert "429" in job["error"]
    assert job["result"] is None


def test_missing_api_key_fails_the_job(monkeypatch):
    def not_configured():
        raise ExtractionNotConfigured("Extraction is not configured. Set GROQ_API_KEY.")

    monkeypatch.setattr(tasks, "create_extractor", not_configured)
    job = client.get(_submit().json()["status_url"]).json()
    assert job["status"] == "failed"
    assert "GROQ_API_KEY" in job["error"]


def test_unreadable_pdf_fails_the_job(fake_model):
    job = client.get(_submit(pdf=b"%PDF-1.7 broken").json()["status_url"]).json()
    assert job["status"] == "failed"
    assert "not a readable PDF" in job["error"]


def test_invalid_profile_is_rejected_before_queueing(fake_model):
    response = _submit('{"name": "X", "registered_capital": -5}')
    assert response.status_code == 422
    with db.session_scope() as session:
        assert session.query(Job).count() == 0


def test_non_pdf_is_rejected(fake_model):
    response = client.post("/api/v1/jobs", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert response.status_code == 415


def test_unknown_job_is_404():
    assert client.get(f"/api/v1/jobs/{uuid.uuid4()}").status_code == 404


def test_queue_down_marks_the_job_failed(monkeypatch):
    def unavailable(job_id):
        raise ConnectionError("redis is down")

    monkeypatch.setattr(tasks.process_tender, "delay", unavailable)
    response = _submit()
    assert response.status_code == 503
    with db.session_scope() as session:
        job = session.query(Job).one()
        assert job.status == JobStatus.FAILED


def test_task_skips_a_job_that_already_ran(fake_model):
    job_id = _submit().json()["id"]
    tasks.process_tender(job_id)  # a redelivered message must not run the job twice
    with db.session_scope() as session:
        assert session.get(Job, uuid.UUID(job_id)).status == JobStatus.SUCCEEDED


def test_progress_is_reported_per_page(fake_model, monkeypatch):
    seen = []
    original = tasks._progress

    def recording(key):
        update = original(key)

        def wrapped(done, total):
            seen.append((done, total))
            update(done, total)

        return wrapped

    monkeypatch.setattr(tasks, "_progress", recording)
    _submit()
    assert seen == [(1, 4), (2, 4), (3, 4), (4, 4)]


def test_result_is_plain_json(fake_model, profile):
    job = client.get(_submit(profile).json()["status_url"]).json()
    json.dumps(job["result"])


GUARANTEE_ANSWER = {
    "answer": "قيمة كفالة دخول العطاء 20,000 دينار أردني.",
    "citations": [{"page": 3, "quote": "كفالة دخول عطاء بقيمة 20,000 دينار أردني"}],
}


@pytest.fixture
def fake_qa():
    llm = FakeLLM(GUARANTEE_ANSWER)
    app.dependency_overrides[get_qa] = lambda: TenderQA(llm, INDEX)
    yield llm
    app.dependency_overrides.pop(get_qa, None)


def test_question_about_a_processed_tender(fake_model, fake_qa):
    job = client.get(_submit().json()["status_url"]).json()
    assert job["result"]["questions_ready"] is True

    response = client.post(
        f"/api/v1/jobs/{job['id']}/questions", json={"question": "ما قيمة كفالة دخول العطاء؟"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "answered"
    assert body["citations"][0]["page"] == 3


def test_question_about_an_unknown_job(fake_qa):
    response = client.post(f"/api/v1/jobs/{uuid.uuid4()}/questions", json={"question": "سؤال؟"})
    assert response.status_code == 404


def test_question_before_the_index_is_ready(fake_model, fake_qa, monkeypatch):
    def broken():
        raise RuntimeError("qdrant is down")

    monkeypatch.setattr(tasks, "get_index", broken)
    job = client.get(_submit().json()["status_url"]).json()
    assert job["status"] == "succeeded"
    assert job["result"]["questions_ready"] is False

    response = client.post(f"/api/v1/jobs/{job['id']}/questions", json={"question": "سؤال؟"})
    assert response.status_code == 409


class OneToolChat:
    """Asks for the qualification report once, then answers."""

    def __init__(self):
        self.replies = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "c1",
                        "type": "function",
                        "function": {"name": "check_qualification", "arguments": "{}"},
                    }
                ],
            },
            {"role": "assistant", "content": "الشركة مؤهلة لهذا العطاء."},
        ]

    def chat(self, messages, tools):
        return self.replies.pop(0)


def test_agent_answers_with_the_engine_report(fake_model, profile):
    job = client.get(_submit(profile).json()["status_url"]).json()
    app.dependency_overrides[get_agent] = lambda: TenderAgent(
        OneToolChat(), TenderQA(FakeLLM(GUARANTEE_ANSWER), INDEX)
    )
    try:
        response = client.post(
            f"/api/v1/jobs/{job['id']}/agent", json={"question": "هل نحن مؤهلون؟"}
        )
    finally:
        app.dependency_overrides.pop(get_agent, None)

    assert response.status_code == 200
    body = response.json()
    assert body["report"]["verdict"] == "qualified"
    assert body["steps"][0]["tool"] == "check_qualification"
