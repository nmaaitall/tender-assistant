from fastapi import APIRouter

from app.api.schemas import HealthResponse
from app.config import settings

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
def health() -> HealthResponse:
    return HealthResponse(status="ok", version=settings.version)
