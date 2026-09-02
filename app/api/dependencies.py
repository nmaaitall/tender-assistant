from functools import lru_cache

from app.domain.rules import QualificationEngine


@lru_cache
def get_engine() -> QualificationEngine:
    return QualificationEngine()
