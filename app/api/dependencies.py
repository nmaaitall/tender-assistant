from functools import lru_cache

from fastapi import HTTPException, status

from app.domain.rules import QualificationEngine
from app.extraction import ExtractionNotConfigured, TenderExtractor, create_extractor


@lru_cache
def get_engine() -> QualificationEngine:
    return QualificationEngine()


def get_extractor() -> TenderExtractor:
    try:
        return create_extractor()
    except ExtractionNotConfigured as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
