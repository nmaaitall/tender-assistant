# Jordan Tender Assistant

Decides whether a small Jordanian contractor should bid on a government tender.
A tender document is parsed into structured requirements, and those requirements
are judged against a stored company profile.

## Core principle

The model extracts, the code judges. An LLM reads the tender document and emits
structured JSON only. The qualification verdict is produced by deterministic
rules in `app/domain/rules`, so every verdict is explainable and reproducible.

## Current state

Domain layer, rule engine and a REST API. No database, no background jobs and no
model call yet.

    app/
      config.py            application settings
      main.py              FastAPI application
      api/
        schemas.py         request and response models
        dependencies.py    engine injection
        routes/            health and qualification endpoints
      domain/
        company.py         company profile model
        tender.py          extracted tender requirements model
        results.py         rule results and qualification report
        rules/             classification, experience and capital rules

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
    POST /api/v1/qualification/evaluate
