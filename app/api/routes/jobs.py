import uuid
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from app.api.dependencies import get_qa
from app.api.uploads import read_upload_bytes
from app.db import get_session
from app.domain.company import CompanyProfile
from app.extraction import LLMError
from app.jobs.models import Job, JobStatus
from app.jobs.tasks import process_tender
from app.qa import Answer, TenderQA

router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobCreated(BaseModel):
    id: uuid.UUID
    status: JobStatus
    status_url: str


class Question(BaseModel):
    question: str = Field(min_length=3, max_length=500, examples=["ما قيمة كفالة دخول العطاء؟"])


class JobView(BaseModel):
    id: uuid.UUID
    status: JobStatus
    filename: str
    page_count: int | None
    pages_done: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None
    result: dict[str, Any] | None


@router.post(
    "",
    response_model=JobCreated,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue a tender PDF for background processing",
    description=(
        "Returns at once with a job id. OCR, extraction and, when a company profile "
        "is sent, the qualification verdict run in a worker. Poll the status URL."
    ),
)
async def create_job(
    response: Response,
    file: UploadFile = File(...),
    profile: str | None = Form(None, description="Optional CompanyProfile as a JSON string"),
    as_of: date | None = Form(None),
    session: Session = Depends(get_session),
) -> JobCreated:
    company = None
    if profile:
        try:
            company = CompanyProfile.model_validate_json(profile)
        except ValidationError as exc:
            raise HTTPException(
                422, exc.errors(include_url=False, include_context=False, include_input=False)
            ) from exc

    data = await read_upload_bytes(file)
    job = Job(
        filename=file.filename or "document.pdf",
        document=data,
        profile=company.model_dump(mode="json") if company else None,
        as_of=as_of,
    )
    session.add(job)
    session.commit()

    try:
        process_tender.delay(str(job.id))
    except Exception as exc:
        job.status = JobStatus.FAILED
        job.error = "The job queue is unavailable."
        session.commit()
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, job.error) from exc

    location = f"/api/v1/jobs/{job.id}"
    response.headers["Location"] = location
    session.refresh(job)
    return JobCreated(id=job.id, status=JobStatus(job.status), status_url=location)


@router.get("/{job_id}", response_model=JobView, summary="Job status, progress and result")
def get_job(job_id: uuid.UUID, session: Session = Depends(get_session)) -> JobView:
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found.")
    return JobView(
        id=job.id,
        status=JobStatus(job.status),
        filename=job.filename,
        page_count=job.page_count,
        pages_done=job.pages_done,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        error=job.error,
        result=job.result,
    )


@router.post(
    "/{job_id}/questions",
    response_model=Answer,
    summary="Ask a question about a processed tender",
    description=(
        "Answers from the tender's own text. Each answer cites quotes and pages that "
        "were checked against the document; status is not_found when the tender does "
        "not say, and unsupported when the model's answer failed the checks."
    ),
)
def ask_question(
    job_id: uuid.UUID,
    body: Question,
    session: Session = Depends(get_session),
    qa: TenderQA = Depends(get_qa),
) -> Answer:
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found.")
    if job.status != JobStatus.SUCCEEDED or not (job.result or {}).get("questions_ready"):
        raise HTTPException(status.HTTP_409_CONFLICT, "This tender is not ready for questions.")
    try:
        return qa.ask(str(job_id), body.question)
    except LLMError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
