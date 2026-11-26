from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _payload(profile, tender, as_of):
    return {
        "profile": profile.model_dump(mode="json"),
        "tender": tender.model_dump(mode="json"),
        "as_of": as_of.isoformat(),
    }


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_evaluate_returns_qualified(profile, tender, today):
    response = client.post("/api/v1/qualification/evaluate", json=_payload(profile, tender, today))
    assert response.status_code == 200
    body = response.json()
    assert body["verdict"] == "qualified"
    assert body["tender_reference"] == "ZM-2026-014"


def test_evaluate_returns_gaps(profile, tender, today):
    profile.registered_capital = None
    response = client.post("/api/v1/qualification/evaluate", json=_payload(profile, tender, today))
    body = response.json()
    assert body["verdict"] == "conditionally_qualified"
    assert body["gaps"][0]["rule_id"] == "registered_capital"


def test_evaluate_rejects_invalid_grade(profile, tender, today):
    payload = _payload(profile, tender, today)
    payload["tender"]["required_classification_grade"] = 9
    response = client.post("/api/v1/qualification/evaluate", json=payload)
    assert response.status_code == 422


def test_openapi_schema_is_served():
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "/api/v1/qualification/evaluate" in response.json()["paths"]


def test_inspect_document_returns_pages():
    pdf = (Path(__file__).parent / "fixtures" / "sample_tender.pdf").read_bytes()
    response = client.post(
        "/api/v1/documents/inspect",
        files={"file": ("sample_tender.pdf", pdf, "application/pdf")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["page_count"] == 4
    assert body["kind"] == "digital"
    assert body["ocr_pages"] == []


def test_inspect_document_rejects_non_pdf():
    response = client.post(
        "/api/v1/documents/inspect",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 415


def test_inspect_document_rejects_empty_file():
    response = client.post(
        "/api/v1/documents/inspect",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    assert response.status_code == 400


def _fake_extractor():
    from app.extraction import TenderExtractor
    from tests.fake_llm import SAMPLE_RESPONSE, FakeLLM

    return TenderExtractor(FakeLLM(SAMPLE_RESPONSE), model_name="fake")


def _sample_pdf():
    return (Path(__file__).parent / "fixtures" / "sample_tender.pdf").read_bytes()


def test_extract_without_api_key_returns_503(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "groq_api_key", None)
    response = client.post(
        "/api/v1/tenders/extract",
        files={"file": ("sample_tender.pdf", _sample_pdf(), "application/pdf")},
    )
    assert response.status_code == 503


def test_extract_returns_requirements_with_citations():
    from app.api.dependencies import get_extractor

    app.dependency_overrides[get_extractor] = _fake_extractor
    try:
        response = client.post(
            "/api/v1/tenders/extract",
            files={"file": ("sample_tender.pdf", _sample_pdf(), "application/pdf")},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["requirements"]["reference"] == "ZM-2026-014"
    assert body["citations"]["min_registered_capital"]["page"] == 2


def test_evaluate_tender_end_to_end(profile, today):
    from app.api.dependencies import get_extractor

    app.dependency_overrides[get_extractor] = _fake_extractor
    try:
        response = client.post(
            "/api/v1/tenders/evaluate",
            files={"file": ("sample_tender.pdf", _sample_pdf(), "application/pdf")},
            data={"profile": profile.model_dump_json(), "as_of": today.isoformat()},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["report"]["verdict"] == "qualified"


def test_evaluate_tender_rejects_bad_profile():
    from app.api.dependencies import get_extractor

    app.dependency_overrides[get_extractor] = _fake_extractor
    try:
        response = client.post(
            "/api/v1/tenders/evaluate",
            files={"file": ("sample_tender.pdf", _sample_pdf(), "application/pdf")},
            data={"profile": '{"name": "X", "registered_capital": -5}'},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422
