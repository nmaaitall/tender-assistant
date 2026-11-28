import pytest
from qdrant_client import QdrantClient

from app.ingestion import ExtractedDocument, PageSource, PageText
from app.retrieval import ChunkIndex, SearchMode, chunk_document, sparse_vector
from app.retrieval.sparse import terms
from evals.retrieval import answer_rank


def _document(*pages: str) -> ExtractedDocument:
    return ExtractedDocument(
        filename="t.pdf",
        page_count=len(pages),
        pages=[
            PageText(page_number=i, source=PageSource.TEXT_LAYER, text=text)
            for i, text in enumerate(pages, start=1)
        ],
    )


class ConceptEmbedder:
    """Maps words to a few concepts, so synonyms land on the same vector."""

    name = "concepts"
    concepts = (
        ("كفالة", "ضمان"),
        ("موعد", "ينتهي", "استلام"),
        ("خبرة", "تعمل", "منذ"),
    )
    dimension = len(concepts) + 1

    def embed_documents(self, texts):
        return [self.embed_query(t) for t in texts]

    def embed_query(self, text):
        vector = [float(any(w in text for w in group)) for group in self.concepts]
        return [*vector, 0.1]


def test_chunks_keep_pages_and_size():
    long_page = "\n".join(f"سطر رقم {i} من شروط العطاء العامة" for i in range(30))
    chunks = chunk_document(_document("الصفحة الأولى", long_page), max_chars=120)

    assert chunks[0].page == 1
    assert {c.page for c in chunks[1:]} == {2}
    assert all(len(c.text) <= 120 for c in chunks)
    assert [c.position for c in chunks] == list(range(len(chunks)))


def test_chunks_repeat_the_last_line():
    page = "\n".join(["أ" * 50, "ب" * 50, "ج" * 50])
    first, second = chunk_document(_document(page), max_chars=110)
    assert first.text.split()[-1] == second.text.split()[0]


def _same_term(a: str, b: str) -> bool:
    return bool(set(terms(a)) & set(terms(b)))


def test_chunks_cut_at_sentence_ends():
    page = "\n".join(
        [
            "يشترط أن يكون المقاول مصنفا في مجال الأبنية",
            ".بالفئة الثالثة أو أعلى لدى دائرة العطاءات الحكومية في المملكة الأردنية الهاشمية",
            "تفرض غرامة تأخير بنسبة 0.1% من قيمة العقد عن كل يوم تأخير في تسليم الأعمال.",
        ]
    )
    first, second = chunk_document(_document(page), min_chars=50)
    assert first.text.endswith("الهاشمية")
    assert "0.1%" in second.text


def test_terms_ignore_prefixes_suffixes_and_stopwords():
    assert _same_term("بالكفالة", "كفالة")
    assert _same_term("وكفالة", "الكفالة")
    assert _same_term("مماثلين", "مماثلة")
    assert _same_term("الأبنية", "أبنية")
    assert not _same_term("كفالة", "مدة")
    assert terms("في من على") == []


def test_query_vector_has_unit_weights():
    indices, values = sparse_vector("كفالة كفالة دخول", query=True)
    assert len(indices) == len(set(indices))
    assert set(values) == {1.0}


@pytest.fixture
def index():
    return ChunkIndex(QdrantClient(":memory:"), ConceptEmbedder())


def test_search_stays_inside_one_document(index):
    index.add("a", chunk_document(_document("كفالة دخول عطاء بقيمة 5,000 دينار")))
    index.add("b", chunk_document(_document("كفالة دخول عطاء بقيمة 9,000 دينار")))

    hits = index.search("a", "كفالة دخول", mode=SearchMode.LEXICAL)
    assert len(hits) == 1
    assert "5,000" in hits[0].text


def test_adding_again_replaces_the_document(index):
    index.add("a", chunk_document(_document("نص قديم عن الكفالة")))
    index.add("a", chunk_document(_document("نص جديد عن الكفالة")))

    hits = index.search("a", "الكفالة", mode=SearchMode.LEXICAL)
    assert [h.text for h in hits] == ["نص جديد عن الكفالة"]


def test_hybrid_finds_a_paraphrase(index):
    index.add(
        "a",
        chunk_document(
            _document(
                "يقدم المقاول كفالة دخول عطاء بقيمة 20,000 دينار",
                "مدة تنفيذ المشروع مئة وثمانون يوما",
            )
        ),
    )
    question = "كم مبلغ الضمان المالي؟"

    assert index.search("a", question, mode=SearchMode.LEXICAL) == []
    hits = index.search("a", question, mode=SearchMode.HYBRID)
    assert hits[0].page == 1


class KeywordReranker:
    name = "keyword"

    def __init__(self, keyword):
        self.keyword = keyword

    def score(self, query, texts):
        return [float(self.keyword in t) for t in texts]


def test_reranker_reorders_candidates():
    index = ChunkIndex(QdrantClient(":memory:"), reranker=KeywordReranker("دخول"))
    index.add(
        "a",
        chunk_document(
            _document("كفالة حسن تنفيذ بنسبة 10% من قيمة العقد", "كفالة دخول عطاء 5,000 دينار")
        ),
    )
    assert index.default_mode is SearchMode.RERANK
    hits = index.search("a", "كفالة", limit=1)
    assert hits[0].page == 2


def test_dense_search_needs_an_embedder():
    index = ChunkIndex(QdrantClient(":memory:"))
    assert index.default_mode is SearchMode.LEXICAL
    with pytest.raises(ValueError):
        index.search("a", "سؤال", mode=SearchMode.DENSE)
    with pytest.raises(ValueError):
        index.search("a", "سؤال", mode=SearchMode.RERANK)


def test_answer_rank():
    texts = ["مدة التنفيذ", "كفالة دخول العطاء"]
    assert answer_rank(texts, ("دخول",)) == 2
    assert answer_rank(texts, ("موعد",)) is None
