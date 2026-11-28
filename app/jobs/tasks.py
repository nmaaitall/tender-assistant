from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

from app.api.uploads import get_ocr
from app.classify import CategoryClassifier
from app.db import session_scope
from app.domain.company import CompanyProfile
from app.domain.rules import QualificationEngine
from app.extraction import ExtractionNotConfigured, LLMError, create_extractor
from app.ingestion import PdfReadError, read_pdf
from app.jobs.models import Job, JobStatus
from app.retrieval import chunk_document
from app.retrieval.factory import get_index
from app.worker import celery_app

log = logging.getLogger(__name__)


class JobFailed(Exception):
    """A failure that ends the job with a message for the user."""


@celery_app.task(name="tenders.process")
def process_tender(job_id: str) -> None:
    key = uuid.UUID(job_id)
    with session_scope() as session:
        job = session.get(Job, key)
        if job is None or job.status != JobStatus.QUEUED:
            return
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(UTC)
        document, filename = job.document, job.filename
        profile, as_of = job.profile, job.as_of

    try:
        result = _run(key, document, filename, profile, as_of)
    except JobFailed as exc:
        _finish(key, JobStatus.FAILED, error=str(exc))
    except Exception as exc:
        _finish(key, JobStatus.FAILED, error=f"Unexpected error: {type(exc).__name__}")
        raise
    else:
        _finish(key, JobStatus.SUCCEEDED, result=result)


def _run(
    key: uuid.UUID,
    data: bytes,
    filename: str,
    profile: dict[str, Any] | None,
    as_of: Any,
) -> dict[str, Any]:
    try:
        document = read_pdf(data, filename, ocr=get_ocr(), on_page=_progress(key))
    except PdfReadError as exc:
        raise JobFailed(str(exc)) from exc

    if not any(page.text for page in document.pages):
        raise JobFailed("No page has readable text. Scanned documents need Tesseract OCR.")

    try:
        extraction = create_extractor().extract(document)
    except (ExtractionNotConfigured, LLMError) as exc:
        raise JobFailed(str(exc)) from exc

    result: dict[str, Any] = {
        "questions_ready": _index(key, document),
        "document": {
            "page_count": document.page_count,
            "kind": document.kind.value,
            "ocr_pages": document.ocr_pages,
            "unreadable_pages": document.unreadable_pages,
        },
        "extraction": extraction.model_dump(mode="json"),
        "category_check": _category_check(document, extraction.requirements.work_category),
        "report": None,
    }
    if profile is not None:
        company = CompanyProfile.model_validate(profile)
        report = QualificationEngine().evaluate(company, extraction.requirements, as_of)
        result["report"] = report.model_dump(mode="json")
    return result


# Below this confidence the classifier's disagreement is not reported.
FLAG_CONFIDENCE = 0.7


@lru_cache
def get_classifier() -> CategoryClassifier | None:
    return CategoryClassifier() if CategoryClassifier.available() else None


def _category_check(document: Any, extracted: Any) -> dict[str, Any] | None:
    """A second opinion on the work category from the trained classifier."""
    classifier = get_classifier()
    if classifier is None or not document.pages:
        return None
    prediction = classifier.predict(document.pages[0].text)
    extracted = extracted.value if extracted is not None else None
    return {
        "predicted": prediction.category,
        "confidence": prediction.confidence,
        "extracted": extracted,
        "flagged": extracted is not None
        and prediction.category != extracted
        and prediction.confidence >= FLAG_CONFIDENCE,
    }


def _index(key: uuid.UUID, document: Any) -> bool:
    """Stores the passages for questions. A failure here does not fail the job."""
    try:
        get_index().add(str(key), chunk_document(document))
    except Exception:
        log.exception("Indexing job %s for questions failed", key)
        return False
    return True


def _progress(key: uuid.UUID):
    def update(done: int, total: int) -> None:
        with session_scope() as session:
            job = session.get(Job, key)
            if job is not None:
                job.pages_done = done
                job.page_count = total

    return update


def _finish(
    key: uuid.UUID,
    status: JobStatus,
    result: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    with session_scope() as session:
        job = session.get(Job, key)
        if job is None:
            return
        job.status = status
        job.result = result
        job.error = error
        job.finished_at = datetime.now(UTC)
