"""Measures how well search finds the passage that answers a question.

No language model is called. Every eval tender, with pages of general contract
conditions added (evals/boilerplate.py), is split into passages and indexed;
then, for each requirement the tender states, two questions are asked: one in the
tender's own wording and one paraphrased with different words. A search succeeds
when a returned passage contains the requirement's evidence words.

Reported per search mode (lexical, dense, hybrid) and question style:
- hit@1, hit@3: the answer passage is first, or in the top three
- MRR: mean reciprocal rank of the first answer passage

Usage:
    python -m evals.retrieval                 lexical only, no model download
    python -m evals.retrieval --dense         adds dense and hybrid (downloads the model)
    python -m evals.retrieval --dense --model google/embeddinggemma-300m
    python -m evals.retrieval --dense --rerank   adds cross-encoder reranking
    python -m evals.retrieval --scanned       scanned copies, read by OCR
    python -m evals.retrieval --misses        list every question not answered first
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path

from qdrant_client import QdrantClient

from app.extraction.verify import compact
from app.ingestion import ExtractedDocument, PageSource, PageText, TesseractOcr, read_pdf
from app.retrieval import (
    ChunkIndex,
    FastEmbedEmbedder,
    FastEmbedReranker,
    SearchMode,
    chunk_document,
)
from app.retrieval.embeddings import DEFAULT_MODEL
from app.retrieval.rerank import DEFAULT_RERANKER
from evals.boilerplate import BOILERPLATE
from evals.cases import CASES

PDFS = Path(__file__).resolve().parent / "pdfs"

# (question in the tender's wording, paraphrase, evidence words in the answer passage)
QUESTIONS = {
    "work_category": (
        "ما هو مجال التصنيف المطلوب؟",
        "في أي نوع من الأعمال يجب أن تكون الشركة معتمدة؟",
        ("مجال",),
    ),
    "required_classification_grade": (
        "ما هي الفئة المطلوبة في التصنيف؟",
        "ما الدرجة التي يجب أن تحملها الشركة؟",
        ("فئة",),
    ),
    "min_registered_capital": (
        "كم يجب أن يكون رأس المال المسجل؟",
        "ما الحد الأدنى لأموال الشركة المسجلة رسميا؟",
        ("رأس المال",),
    ),
    "min_similar_projects": (
        "كم عدد المشاريع المماثلة المطلوبة؟",
        "كم عملا سابقا مشابها يجب أن تكون الشركة قد أنجزته؟",
        ("مماثل",),
    ),
    "min_years_experience": (
        "كم سنة خبرة مطلوبة؟",
        "كم سنة يجب أن تكون الشركة قد عملت في هذا النوع من الأعمال؟",
        ("خبرة",),
    ),
    "submission_deadline": (
        "ما هو آخر موعد لتقديم العروض؟",
        "متى ينتهي استلام الطلبات؟",
        ("موعد", "الإغلاق"),
    ),
    "bid_guarantee_amount": (
        "ما قيمة كفالة دخول العطاء؟",
        "كم مبلغ الضمان المالي الذي يرفق مع العرض؟",
        ("دخول",),
    ),
}
STYLES = ("wording", "paraphrase")


@dataclass
class Tally:
    ranks: list[int | None] = field(default_factory=list)

    def hit(self, k: int) -> float:
        return sum(1 for r in self.ranks if r is not None and r <= k) / len(self.ranks)

    def mrr(self) -> float:
        return sum(1 / r for r in self.ranks if r is not None) / len(self.ranks)


def answer_rank(texts: list[str], evidence: tuple[str, ...]) -> int | None:
    for rank, text in enumerate(texts, start=1):
        page = compact(text)
        if any(compact(word) in page for word in evidence):
            return rank
    return None


def with_boilerplate(document: ExtractedDocument) -> ExtractedDocument:
    start = document.page_count + 1
    extra = [
        PageText(page_number=start + i, source=PageSource.TEXT_LAYER, text=text)
        for i, text in enumerate(BOILERPLATE)
    ]
    pages = document.pages + extra
    return document.model_copy(update={"pages": pages, "page_count": len(pages)})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dense", action="store_true", help="also run dense and hybrid")
    parser.add_argument("--scanned", action="store_true", help="use the scanned copies")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="embedding model for --dense")
    parser.add_argument("--rerank", action="store_true", help="also rerank with a cross-encoder")
    parser.add_argument("--reranker", default=DEFAULT_RERANKER)
    parser.add_argument("--misses", action="store_true", help="list questions not ranked first")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    if args.scanned and not TesseractOcr.available():
        raise SystemExit("Tesseract is not installed: brew install tesseract tesseract-lang")
    source = PDFS / "scanned" if args.scanned else PDFS
    ocr = TesseractOcr() if args.scanned else None

    embedder = FastEmbedEmbedder(args.model) if args.dense else None
    reranker = FastEmbedReranker(args.reranker) if args.rerank else None
    index = ChunkIndex(QdrantClient(":memory:"), embedder, reranker=reranker)
    modes = [SearchMode.LEXICAL]
    if embedder:
        modes += [SearchMode.DENSE, SearchMode.HYBRID]
    if reranker:
        modes.append(SearchMode.RERANK)

    tallies = {(m, s): Tally() for m in modes for s in STYLES}
    misses: list[str] = []
    for case in CASES:
        document = read_pdf((source / f"{case['id']}.pdf").read_bytes(), case["id"], ocr=ocr)
        index.add(case["id"], chunk_document(with_boilerplate(document)))
        for name, (wording, paraphrase, evidence) in QUESTIONS.items():
            if case["expected"][name] is None:
                continue
            for style, question in zip(STYLES, (wording, paraphrase), strict=True):
                for mode in modes:
                    hits = index.search(case["id"], question, limit=args.limit, mode=mode)
                    rank = answer_rank([h.text for h in hits], evidence)
                    tallies[(mode, style)].ranks.append(rank)
                    if rank != 1:
                        misses.append(f"{mode:<8} {style:<10} {case['id']:<24} {name} rank={rank}")

    if embedder:
        print(f"Embedding model: {embedder.name}")
    if reranker:
        print(f"Reranker: {reranker.name}")
    print(f"{'mode':<8} {'questions':<10} {'hit@1':>7} {'hit@3':>7} {'MRR':>7}  n")
    for (mode, style), tally in tallies.items():
        print(
            f"{mode:<8} {style:<10} {tally.hit(1):>7.1%} {tally.hit(3):>7.1%}"
            f" {tally.mrr():>7.3f}  {len(tally.ranks)}"
        )
    if args.misses and misses:
        print("\nNot ranked first:")
        print("\n".join(misses))


if __name__ == "__main__":
    main()
