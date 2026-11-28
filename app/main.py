from fastapi import FastAPI

from app.api.routes import documents, health, jobs, qualification, tenders
from app.config import settings

app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description=(
        "Decides whether a Jordanian contractor should bid on a government tender. "
        "The model extracts structured requirements; this service judges them."
    ),
)

app.include_router(health.router)
app.include_router(documents.router, prefix=settings.api_prefix)
app.include_router(tenders.router, prefix=settings.api_prefix)
app.include_router(jobs.router, prefix=settings.api_prefix)
app.include_router(qualification.router, prefix=settings.api_prefix)
