from __future__ import annotations

from app.domain.enums import WorkCategory
from app.ingestion import ExtractedDocument

FIELDS = {
    "reference": "tender reference number, as written",
    "title": "short title of the works",
    "work_category": (
        "the classification field the contractor must be registered in, usually written "
        "next to the required grade as مجال ... (for example مجال الأبنية is buildings). "
        "One of: " + ", ".join(c.value for c in WorkCategory)
    ),
    "required_classification_grade": "minimum contractor grade, integer 1-6 (1 is highest)",
    "min_registered_capital": "minimum registered capital in JOD, number",
    "min_similar_projects": "minimum number of similar completed projects, integer",
    "min_similar_project_value": "minimum value of each similar project in JOD, number",
    "experience_lookback_years": "window in years for similar projects, integer",
    "min_years_experience": "minimum years of experience, integer",
    "submission_deadline": "bid submission deadline, YYYY-MM-DD",
    "bid_guarantee_amount": "bid bond amount in JOD, number",
}

SYSTEM_PROMPT = f"""You extract requirements from Jordanian government tender documents
written in Arabic.

Return one JSON object with two keys:
- "fields": an object whose keys are taken from the list below. Each value is
  {{"value": ..., "page": <page number>, "quote": "<exact sentence from that page>"}}.
  Leave a field out when the document does not state it. Never guess.
- "required_documents": a list of
  {{"name": "<document name in Arabic>", "page": ..., "quote": "..."}}.

Fields:
{chr(10).join(f"- {name}: {hint}" for name, hint in FIELDS.items())}

Rules:
- The quote must be copied from the page text exactly as it appears, without correcting it.
- Numbers are plain numbers without commas or currency.
- Page numbers come from the [page N] markers.
- Check every field in the list. Leaving out a field the document does state is an error.
"""


def build_user_prompt(document: ExtractedDocument) -> str:
    return f"Tender document:\n\n{document.full_text()}"
