from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.agent import TenderAgent
from app.config import settings
from app.domain.rules import QualificationEngine
from app.extraction import ExtractionNotConfigured, GroqClient, TenderExtractor, create_extractor
from app.qa import TenderQA
from app.retrieval.factory import get_index


@lru_cache
def get_engine() -> QualificationEngine:
    return QualificationEngine()


def get_extractor() -> TenderExtractor:
    try:
        return create_extractor()
    except ExtractionNotConfigured as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc


def get_qa() -> TenderQA:
    if not settings.groq_api_key:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Questions are not configured. Set GROQ_API_KEY."
        )
    client = GroqClient(settings.groq_api_key, settings.groq_model, settings.llm_timeout_seconds)
    return TenderQA(client, get_index())


def get_agent(qa: Annotated[TenderQA, Depends(get_qa)]) -> TenderAgent:
    client = GroqClient(settings.groq_api_key, settings.groq_model, settings.llm_timeout_seconds)
    return TenderAgent(client, qa)
