from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, ValidationError

from app.api.dependencies import get_engine, get_extractor
from app.api.uploads import read_pdf_upload
from app.domain.company import CompanyProfile
from app.domain.results import QualificationReport
from app.domain.rules import QualificationEngine
from app.extraction import ExtractionResult, LLMError, TenderExtractor
from app.ingestion import ExtractedDocument

router = APIRouter(prefix="/tenders", tags=["tenders"])


class TenderEvaluation(BaseModel):
    extraction: ExtractionResult
    report: QualificationReport


def _extract(document: ExtractedDocument, extractor: TenderExtractor) -> ExtractionResult:
    if not any(page.text for page in document.pages):
        raise HTTPException(
            422,
            "No page has readable text. Scanned documents need Tesseract OCR installed.",
        )
    try:
        return extractor.extract(document)
    except LLMError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc


@router.post(
    "/extract",
    response_model=ExtractionResult,
    summary="Extract structured requirements from a tender PDF",
    description=(
        "The model proposes each requirement with a page number and a quote. "
        "Values whose quote is not found on the cited page are rejected."
    ),
)
async def extract_tender(
    file: UploadFile = File(...),
    extractor: TenderExtractor = Depends(get_extractor),
) -> ExtractionResult:
    document = await read_pdf_upload(file)
    return _extract(document, extractor)


@router.post(
    "/evaluate",
    response_model=TenderEvaluation,
    summary="Upload a tender PDF and a company profile, get a qualification verdict",
)
async def evaluate_tender(
    file: UploadFile = File(...),
    profile: str = Form(..., description="CompanyProfile as a JSON string"),
    as_of: date | None = Form(None),
    extractor: TenderExtractor = Depends(get_extractor),
    engine: QualificationEngine = Depends(get_engine),
) -> TenderEvaluation:
    try:
        company = CompanyProfile.model_validate_json(profile)
    except ValidationError as exc:
        raise HTTPException(
            422, exc.errors(include_url=False, include_context=False, include_input=False)
        ) from exc

    document = await read_pdf_upload(file)
    extraction = _extract(document, extractor)
    report = engine.evaluate(company, extraction.requirements, as_of)
    return TenderEvaluation(extraction=extraction, report=report)
