# Jordan Tender Assistant

Decides whether a small Jordanian contractor should bid on a government tender.
A tender document is parsed into structured requirements, and those requirements
are judged against a stored company profile.

## Core principle

The model extracts, the code judges. An LLM reads the tender document and emits
structured JSON only. The qualification verdict is produced by deterministic
rules in `app/domain/rules`, so every verdict is explainable and reproducible.

## Current state

Domain layer, rule engine, PDF ingestion with Arabic OCR, LLM extraction, an eval
suite and a REST API. No database and no background jobs yet.

    app/
      config.py            application settings
      main.py              FastAPI application
      api/
        schemas.py         request and response models
        dependencies.py    engine injection
        routes/            health and qualification endpoints
      ingestion/
        pdf_reader.py      page-by-page text extraction, OCR routing
        ocr.py             Tesseract OCR engine
        text_quality.py    Arabic normalization and garbled-text detection
        models.py          extracted document and page models
      extraction/
        llm.py             model client protocol and the Groq client
        prompt.py          extraction prompt
        extractor.py       model output to TenderRequirements, with checks
        verify.py          quote matching against the page text
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

Pages without a usable text layer are read by Tesseract OCR (Arabic and English).
Each page is rendered at the resolution of the scan itself and cleaned with a median
filter before OCR; upscaling a low-resolution scan was measured to lower accuracy.
OCR output that mixes Latin and Arabic-Indic digits inside one number is replaced
with `[غير مقروء]`, because those tokens are misreads that look like valid amounts
(120,000 read as 11,210). Without Tesseract installed, scanned pages stay flagged
as `needs_ocr`.

    macOS:  brew install tesseract tesseract-lang
    Debian: apt-get install tesseract-ocr tesseract-ocr-ara

Known limitation: Word and LibreOffice exports often store the lam-alef ligature
in reverse, so `الأولى` reads as `األولى`. The text stays usable for the model;
OCR does not have this problem.

The test fixture `tests/fixtures/sample_tender.pdf` is a synthetic Arabic tender
built from `scripts/sample_tender.html` with `make sample-tender` (needs LibreOffice).

## Extraction

The model returns every requirement with the page it was found on and a quote from
that page. Before a value is used:

- the quote must be found on the cited page (spacing, punctuation, alef forms and the
  reversed lam-alef ligature are ignored)
- money amounts must also appear in the quote
- the value must fit the field type

Anything that fails is dropped and listed under `rejected`, so the rule engine only
ever sees values that can be traced back to the document. A dropped requirement
makes the verdict `conditionally_qualified` rather than a guess.

The model is reached through the `LLMClient` protocol, so the provider can change
without touching the extractor. Groq is the current implementation.

## Evals

`evals/` holds 12 synthetic Arabic tenders with known answers. Each case targets a
specific difficulty: roads, water, electromechanical and other fields; grades 1 to 5;
amounts from 2,500 to 10,000,000 JOD; requirements that are not stated at all;
distracting amounts (performance bond, insurance, delay penalty); amounts written in
words; label: value layouts; Arabic-Indic digits; requirements spread over five pages.

    python -m evals.run
    python -m evals.run --cases c02_roads c10_arabic_digits
    python -m evals.run --scanned      scanned copies, read by OCR
    python -m evals.ocr_quality        OCR accuracy only, no model call

Every field is scored as correct, correctly absent, missed, wrong or spurious. Wrong
and spurious values are the ones that reach the rule engine, so they are reported
separately as unsafe values. Each case is also judged against one fixed company
profile and the verdict is compared with the verdict the correct answers produce.

Results with `openai/gpt-oss-120b` on Groq:

| Run | Field accuracy | Precision | Unsafe values | Verdict agreement |
|---|---|---|---|---|
| Digital, baseline | 97.5% | 100% | 0 | 12/12 |
| Digital, after matching fixes | 99.2% | 100% | 0 | 12/12 |
| Scanned, OCR | 91.7% | 100% | 0 | 11/12 |

The scanned copies are image-only PDFs with scan damage (tilt, blur, speckle noise,
150 dpi, JPEG compression), built with `python scripts/build_scanned_eval_set.py`.
On them OCR reaches 97.6% character accuracy against 98.2% for the digital text
layer, and keeps 39 of 45 amounts and dates intact.

On scans, recall drops because damaged numbers are rejected rather than guessed: a
number cut at a line start (400,000 read as 0) fails the minimum-amount check, and
Arabic-Indic numbers that OCR mangles are marked unreadable. Every lost value fails
safe as missed, so precision stays at 100%. The one verdict that differs is
conditionally qualified instead of qualified, which asks for a manual check rather
than giving a wrong answer.

Remaining risk: OCR can misread Latin digits into another valid-looking number
(120,000 read as 10000 in one case). The quote check cannot catch this, because the
wrong number is then really on the page. The model did not use it in this run.

The first run surfaced three real issues, all fixed: Arabic-Indic numbers stored in
reverse by the PDF producer, quotes of a single date, and words split or glued by the
text layer around tanween. The PDFs are rebuilt with `python scripts/build_eval_set.py`.

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

## Configuration

Copy `.env.example` to `.env` and set `GROQ_API_KEY`. Without it the extraction
endpoints return 503 and everything else works.

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
    POST /api/v1/tenders/extract
    POST /api/v1/tenders/evaluate
    POST /api/v1/qualification/evaluate
