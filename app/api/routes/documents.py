from fastapi import APIRouter, File, UploadFile

from app.api.uploads import read_pdf_upload
from app.ingestion import ExtractedDocument

router = APIRouter(prefix="/documents", tags=["documents"])


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
    return await read_pdf_upload(file)
