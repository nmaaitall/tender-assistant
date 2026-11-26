from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.config import settings
from app.ingestion import ExtractedDocument, PdfReadError, read_pdf

router = APIRouter(prefix="/documents", tags=["documents"])

_PDF_MAGIC = b"%PDF-"


@router.post(
    "/inspect",
    response_model=ExtractedDocument,
    summary="Read a tender PDF page by page",
    description=(
        "Extracts the text layer of every page and flags pages that need OCR, "
        "either because they have no text (scans) or because the text layer is garbled."
    ),
)
async def inspect_document(file: UploadFile = File(...)) -> ExtractedDocument:
    data = await file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024

    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The uploaded file is empty.")
    if len(data) > max_bytes:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"The file is larger than {settings.max_upload_mb} MB.",
        )
    if not data.startswith(_PDF_MAGIC):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Only PDF files are accepted.")

    try:
        return read_pdf(data, filename=file.filename or "document.pdf")
    except PdfReadError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
