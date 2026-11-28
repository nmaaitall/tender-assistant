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
suite, background jobs (Celery and Redis) with results stored in Postgres, and a
REST API.

    app/
      config.py            application settings
      main.py              FastAPI application
      db.py                SQLAlchemy engine and sessions
      worker.py            Celery application
      jobs/
        models.py          job table: upload, status, progress, result
        tasks.py           background task: OCR, extraction, verdict
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
      retrieval/
        chunking.py        page-bound passages
        sparse.py          Arabic lexical vectors
        embeddings.py      multilingual sentence embeddings (ONNX, CPU)
        index.py           Qdrant storage and lexical, dense or hybrid search
        rerank.py          cross-encoder reranking
        factory.py         index built from settings
      qa/
        answerer.py        answers from retrieved passages, with checked citations
        prompt.py          question answering prompt
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

Requirements the first reading leaves out or gets rejected are asked for once more,
with the rejection reason. If a requirement is still missing but its wording is in
the document (for example خبرة or رأس المال), it is marked unverified, so a rule
cannot pass on a requirement the model overlooked. The eval report counts model
calls per tender and splits verdict mismatches into cautious (conditionally
qualified, a manual check) and wrong.

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

| Run | Field accuracy | Precision | Unsafe values | Verdicts (match / cautious / wrong) | Calls per tender |
|---|---|---|---|---|---|
| Digital, baseline | 97.5% | 100% | 0 | 12 / 0 / 0 | 1 |
| Digital, after matching fixes | 99.2% | 100% | 0 | 12 / 0 / 0 | 1 |
| Digital, second pass | 100% | 100% | 0 | 12 / 0 / 0 | 1.25 |
| Scanned, OCR | 91.7% | 100% | 0 | 11 / 1 / 0 | 1 |
| Scanned, second pass | 94.2% | 100% | 0 | 10 / 2 / 0 | 1.58 |

The scanned copies are image-only PDFs with scan damage (tilt, blur, speckle noise,
150 dpi, JPEG compression), built with `python scripts/build_scanned_eval_set.py`.
On them OCR reaches 97.6% character accuracy against 98.2% for the digital text
layer, and keeps 39 of 45 amounts and dates intact.

On scans, recall drops because damaged numbers are rejected rather than guessed: a
number cut at a line start (400,000 read as 0) fails the minimum-amount check, and
Arabic-Indic numbers that OCR mangles are marked unreadable. Every lost value fails
safe as missed, so precision stays at 100%. Verdicts that differ are conditionally
qualified instead of the expected verdict, which asks for a manual check rather than
giving a wrong answer.

The second pass recovers some of these values and costs about 0.25 extra calls per
tender on digital files and 0.6 on scans. It also adds one cautious verdict on scans:
a missed years-of-experience requirement that used to let the experience rule pass
is now marked unverified.

Remaining risk: OCR can misread Latin digits into another valid-looking number
(120,000 read as 10000 in one case). The quote check cannot catch this, because the
wrong number is then really on the page. The model did not use it in this run.

The first run surfaced three real issues, all fixed: Arabic-Indic numbers stored in
reverse by the PDF producer, quotes of a single date, and words split or glued by the
text layer around tanween. The PDFs are rebuilt with `python scripts/build_eval_set.py`.

## Retrieval

Questions about a tender are answered from its own text, so the first step is
finding the right passage. Each page is split into passages of one or two sentences
that never cross a page, so an answer cites one page and one requirement.

Every passage is stored in Qdrant with two vectors:

- lexical: words normalized like the citation check, with the article and common
  suffixes removed (بالكفالة and كفالة, مماثلة and مماثلين match); Qdrant applies IDF
- dense: a multilingual embedding model, run on CPU through ONNX

Hybrid search runs both and merges them with reciprocal rank fusion. The top 20
are then reranked by a multilingual cross-encoder (`bge-reranker-v2-m3`, int8), which
reads the question and each passage together.

`python -m evals.retrieval` asks two questions for every stated requirement in the
eval tenders: one in the tender's wording and one paraphrased. Sixteen pages of
general contract conditions (performance bond, delay penalties, insurance, required
certificates) are added to every tender, because a real tender is long and shares
many words with the questions. A search counts as a hit when a returned passage
holds the requirement.

    python -m evals.retrieval              lexical only
    python -m evals.retrieval --dense      lexical, dense and hybrid
    python -m evals.retrieval --dense --model google/embeddinggemma-300m
    python -m evals.retrieval --dense --rerank
    python -m evals.retrieval --scanned    scanned copies, read by OCR

Share of questions whose answer passage is ranked first (hit@1) or in the top three
(hit@3), on the digital tenders:

| Search | Tender wording hit@1 | hit@3 | Paraphrased hit@1 | hit@3 |
|---|---|---|---|---|
| Lexical | 88.9% | 98.8% | 13.6% | 19.8% |
| Dense, MiniLM-L12 | 38.3% | 77.8% | - | - |
| Dense, Qwen3-Embedding-0.6B | 66.7% | 96.3% | - | - |
| Dense, embeddinggemma-300m | 82.7% | 98.8% | 17.3% | 66.7% |
| Hybrid, embeddinggemma | 90.1% | 98.8% | 14.8% | 38.3% |
| Hybrid + reranker | 96.3% | 98.8% | 38.3% | 72.8% |

MiniLM and Qwen3 were compared on the tender-wording questions only; they were
dropped before one ambiguous paraphrase was rewritten (see Questions).

The first dense model, MiniLM, truncates at 128 tokens and missed requirements at the
end of long passages; splitting by sentence and moving to embeddinggemma fixed most of
that. Paraphrased questions remain the hard case: the nearest wrong passage is usually
a look-alike clause (performance bond for bid bond, contract duration for the
submission deadline), which the reranker separates best.

## Questions

`TenderQA` answers a question about one indexed tender. The five best passages go
to the model with the question; it answers from them only, cites a quote and page
for each fact, or returns nothing when the passages do not say. Before an answer is
returned:

- every quote must be found in a passage from the cited page
- every amount or year in the answer must appear in a cited quote
- an answer with no valid citation is reported as `unsupported`, never as fact

`python -m evals.qa` asks every eval tender about each requirement, about the
requirements it does not state, and two questions no tender answers (the price of
the tender documents, alternative offers). Answers are scored as correct, wrong,
missed, refused or invented; wrong and invented answers are the unsafe ones.

    python -m evals.qa                     hybrid search with reranking
    python -m evals.qa --paraphrase        paraphrased questions
    python -m evals.qa --lexical           lexical search only

Results with `openai/gpt-oss-120b`, hybrid search and reranking, questions in the
tender's wording:

| Answer accuracy | Refusals | Unsafe answers | Unsupported |
|---|---|---|---|
| 98.8% (80 of 81) | 100% (27 of 27) | 0 | 0 |

The one miss is a tender that writes تاريخ الإغلاق instead of آخر موعد لتقديم
العروض; the model answered not found rather than guess.

A first run with paraphrased questions showed one question was ambiguous: "منذ متى
يجب أن تعمل الشركة" also asks when work starts, which the contract start clause
answers, and the model cited that clause. The question was rewritten to ask for
years of experience. The scorer also missed counts written as words with tanween
(عملاً واحداً); it was fixed and tested.

Once a job has finished, questions go to `POST /api/v1/jobs/{id}/questions`:

    {"question": "ما قيمة كفالة دخول العطاء؟"}

The worker stores the tender's passages in Qdrant while it processes the job. If
that fails, the job still succeeds with `questions_ready: false` and the endpoint
answers 409.

## Background jobs

OCR takes about half a second per page, so a long tender is too slow for one HTTP
request. `POST /api/v1/jobs` stores the PDF and returns `202 Accepted` with a job id
at once; a Celery worker runs OCR, extraction and, when a company profile is sent,
the verdict. `GET /api/v1/jobs/{id}` reports status, pages done and the result.

- Redis carries the task messages only. Status, progress and results live in
  Postgres, so the API answers without asking Celery.
- Tasks are acknowledged after they finish, so a worker crash requeues the job, and a
  task that finds its job already started does nothing, so a redelivered message
  cannot run a job twice.
- If the queue is down the upload is refused with 503 and the job is kept as failed
  with the reason, rather than lost.
- The schema is managed with Alembic. A test checks that the migrations build the
  same tables as the models.

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

## Run with Docker Compose

    docker compose up --build

Starts the API on port 8000, a worker, Postgres, Redis and Qdrant. The embedding and
reranker models (about 1.8 GB) are downloaded on first use into a shared volume. The API applies database
migrations on start.

## Run locally

    python3.12 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements-dev.txt
    pytest
    alembic upgrade head
    uvicorn app.main:app --reload

Locally the database is a SQLite file. Jobs need a worker and Redis:

    brew install redis && brew services start redis
    celery -A app.worker worker --loglevel=info

Or set `CELERY_EAGER=true` in `.env` to run jobs inside the API process without
Redis or a worker. Without `QDRANT_URL`, passages are stored in `./qdrant_data`, a
folder only one process can open, so local question answering needs eager jobs.

Interactive documentation: http://localhost:8000/docs

## API

    GET  /health
    POST /api/v1/documents/inspect
    POST /api/v1/tenders/extract
    POST /api/v1/tenders/evaluate
    POST /api/v1/jobs
    GET  /api/v1/jobs/{id}
    POST /api/v1/jobs/{id}/questions
    POST /api/v1/qualification/evaluate
