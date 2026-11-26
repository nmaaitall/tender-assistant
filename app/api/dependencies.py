from functools import lru_cache

from fastapi import HTTPException, status

from app.config import settings
from app.domain.rules import QualificationEngine
from app.extraction import GroqClient, TenderExtractor


@lru_cache
def get_engine() -> QualificationEngine:
    return QualificationEngine()


def get_extractor() -> TenderExtractor:
    if not settings.groq_api_key:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Extraction is not configured. Set GROQ_API_KEY.",
        )
    client = GroqClient(settings.groq_api_key, settings.groq_model, settings.llm_timeout_seconds)
    return TenderExtractor(client, model_name=settings.groq_model)
