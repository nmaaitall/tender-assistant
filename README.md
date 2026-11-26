# Jordan Tender Assistant

Decides whether a small Jordanian contractor should bid on a government tender.
A tender document is parsed into structured requirements, and those requirements
are judged against a stored company profile.

## Core principle

The model extracts, the code judges. An LLM reads the tender document and emits
structured JSON only. The qualification verdict is produced by deterministic
rules in `app/domain/rules`, so every verdict is explainable and reproducible.

## Current state

Domain layer, rule engine, PDF ingestion and a REST API. No database, no background
jobs, no OCR and no model call yet.

    app/
      config.py            application settings
      main.py              FastAPI application
      api/
        schemas.py         request and response models
        dependencies.py    engine injection
        routes/            health and qualification endpoints
      ingestion/
        pdf_reader.py      page-by-page text extraction, OCR routing
        text_quality.py    Arabic normalization and garbled-text detection
        models.py          extracted document and page models
      domain/
        company.py         company profile model
        tender.py          extracted tender requirements model
        results.py         rule results and qualification report
        rules/             classification, experience and capital rules

## Ingestion

Every page of an uploaded PDF is read separately and given a source:

- `text_layer` - the page has a usable text layer; the text is normalized
  (presentation forms, tashkeel, tatweel, bidi controls, spacing around numbers)
- `needs_ocr` - the page has no text (a scan) or its text layer is garbled
  (a broken font map that yields characters from unrelated scripts)

The document is then `digital`, `scanned` or `mixed`. Page numbers are kept so
answers can cite the page they come from.

Known limitation: Word and LibreOffice exports often store the lam-alef ligature
in reverse, so `الأولى` reads as `األولى`. The text stays usable for the model;
OCR does not have this problem.

The test fixture `tests/fixtures/sample_tender.pdf` is a synthetic Arabic tender
built from `scripts/sample_tender.html` with `make sample-tender` (needs LibreOffice).

## Rules

Three rules run against every tender, following the Government Tenders
Department classification system: six contractor grades where grade 1 is the
highest, across five fields (roads, buildings, electromechanical, water and
sewerage, other works).

- `classification` - the company holds a sufficient grade in the tender field
- `experience` - years of activity and comparable projects within a lookback window
- `registered_capital` - capital meets the stated minimum

Each rule returns `passed`, `failed`, `unknown` (the profile does not state the
data) or `not_applicable` (the tender does not state the requirement).

## Verdicts

- `qualified` - every stated requirement is met
- `conditionally_qualified` - a requirement cannot be checked because the profile
  is missing data
- `not_qualified` - at least one requirement fails

## Run locally

    python3.12 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements-dev.txt
    pytest
    uvicorn app.main:app --reload

Interactive documentation: http://localhost:8000/docs

## Run with Docker

    docker compose up --build

## API

    GET  /health
    POST /api/v1/documents/inspect
    POST /api/v1/qualification/evaluate
