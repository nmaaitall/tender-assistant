from fastapi import HTTPException, UploadFile, status

from app.config import settings
from app.ingestion import ExtractedDocument, OcrEngine, PdfReadError, TesseractOcr, read_pdf

_PDF_MAGIC = b"%PDF-"


def get_ocr() -> OcrEngine | None:
    if settings.ocr_enabled and TesseractOcr.available():
        return TesseractOcr()
    return None


async def read_pdf_upload(file: UploadFile) -> ExtractedDocument:
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
        return read_pdf(data, filename=file.filename or "document.pdf", ocr=get_ocr())
    except PdfReadError as exc:
        raise HTTPException(422, str(exc)) from exc
