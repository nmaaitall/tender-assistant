from fastapi import APIRouter, Depends

from app.api.dependencies import get_engine
from app.api.schemas import EvaluationRequest
from app.domain.results import QualificationReport
from app.domain.rules import QualificationEngine

router = APIRouter(prefix="/qualification", tags=["qualification"])


@router.post(
    "/evaluate",
    response_model=QualificationReport,
    summary="Judge a company profile against extracted tender requirements",
    description=(
        "Runs the deterministic rule engine. No language model is called here: "
        "the request already carries structured tender requirements."
    ),
)
def evaluate(
    payload: EvaluationRequest,
    engine: QualificationEngine = Depends(get_engine),
) -> QualificationReport:
    return engine.evaluate(payload.profile, payload.tender, payload.as_of)
