from app.config import settings
from app.extraction.extractor import TenderExtractor
from app.extraction.llm import GroqClient


class ExtractionNotConfigured(RuntimeError):
    """No model credentials are set."""


def create_extractor() -> TenderExtractor:
    if not settings.groq_api_key:
        raise ExtractionNotConfigured("Extraction is not configured. Set GROQ_API_KEY.")
    client = GroqClient(settings.groq_api_key, settings.groq_model, settings.llm_timeout_seconds)
    return TenderExtractor(client, model_name=settings.groq_model)
