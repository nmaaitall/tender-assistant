"""Stores tender passages in Qdrant and searches them.

Each passage has a lexical vector and, when an embedder is set, a dense vector.
Hybrid search runs both and merges the rankings with reciprocal rank fusion, so a
passage that uses the exact tender wording and one that only means the same thing
can both be found. With a reranker, the hybrid candidates are rescored by a
cross-encoder that reads the question and each passage together.
"""

from __future__ import annotations

import uuid
import warnings
from enum import StrEnum

from pydantic import BaseModel
from qdrant_client import QdrantClient, models

from app.retrieval.chunking import Chunk
from app.retrieval.embeddings import Embedder
from app.retrieval.rerank import Reranker
from app.retrieval.sparse import sparse_vector

COLLECTION = "tender_chunks"
DENSE = "dense"
LEXICAL = "lexical"
RERANK_CANDIDATES = 20


class SearchMode(StrEnum):
    LEXICAL = "lexical"
    DENSE = "dense"
    HYBRID = "hybrid"
    RERANK = "rerank"


class Hit(BaseModel):
    page: int
    position: int
    text: str
    score: float


class ChunkIndex:
    def __init__(
        self,
        client: QdrantClient,
        embedder: Embedder | None = None,
        collection: str | None = None,
        reranker: Reranker | None = None,
    ) -> None:
        self.client = client
        self.embedder = embedder
        self.reranker = reranker
        # Vectors from different models cannot share a collection.
        self.collection = collection or _collection_name(embedder)
        self._ensure_collection()

    @property
    def default_mode(self) -> SearchMode:
        if self.reranker:
            return SearchMode.RERANK
        return SearchMode.HYBRID if self.embedder else SearchMode.LEXICAL

    def add(self, document_id: str, chunks: list[Chunk]) -> None:
        self.delete(document_id)
        if not chunks:
            return
        dense = self.embedder.embed_documents([c.text for c in chunks]) if self.embedder else None
        points = []
        for i, chunk in enumerate(chunks):
            indices, values = sparse_vector(chunk.text)
            vector: dict = {LEXICAL: models.SparseVector(indices=indices, values=values)}
            if dense is not None:
                vector[DENSE] = dense[i]
            points.append(
                models.PointStruct(
                    id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{document_id}/{chunk.position}")),
                    vector=vector,
                    payload={"document_id": document_id, **chunk.model_dump()},
                )
            )
        self.client.upsert(self.collection, points=points)

    def delete(self, document_id: str) -> None:
        self.client.delete(
            self.collection, points_selector=models.FilterSelector(filter=_only(document_id))
        )

    def search(
        self,
        document_id: str,
        query: str,
        limit: int = 5,
        mode: SearchMode | None = None,
    ) -> list[Hit]:
        mode = mode or self.default_mode
        if mode is SearchMode.RERANK:
            return self._rerank(document_id, query, limit)
        if mode is not SearchMode.LEXICAL and self.embedder is None:
            raise ValueError(f"{mode} search needs an embedder")
        doc_filter = _only(document_id)
        if mode is SearchMode.HYBRID:
            response = self.client.query_points(
                self.collection,
                prefetch=[
                    self._lexical(query, doc_filter, limit * 4),
                    self._dense(query, doc_filter, limit * 4),
                ],
                query=models.FusionQuery(fusion=models.Fusion.RRF),
                limit=limit,
            )
        else:
            single = self._lexical if mode is SearchMode.LEXICAL else self._dense
            prefetch = single(query, doc_filter, limit)
            response = self.client.query_points(
                self.collection,
                query=prefetch.query,
                using=prefetch.using,
                query_filter=doc_filter,
                limit=limit,
            )
        return [
            Hit(
                page=p.payload["page"],
                position=p.payload["position"],
                text=p.payload["text"],
                score=p.score,
            )
            for p in response.points
        ]

    def _rerank(self, document_id: str, query: str, limit: int) -> list[Hit]:
        if self.reranker is None:
            raise ValueError("rerank search needs a reranker")
        first = SearchMode.HYBRID if self.embedder else SearchMode.LEXICAL
        candidates = self.search(document_id, query, RERANK_CANDIDATES, first)
        if not candidates:
            return []
        scores = self.reranker.score(query, [c.text for c in candidates])
        ranked = sorted(zip(scores, candidates, strict=True), key=lambda pair: -pair[0])
        return [hit.model_copy(update={"score": score}) for score, hit in ranked[:limit]]

    def _lexical(self, query: str, doc_filter: models.Filter, limit: int) -> models.Prefetch:
        indices, values = sparse_vector(query, query=True)
        return models.Prefetch(
            query=models.SparseVector(indices=indices, values=values),
            using=LEXICAL,
            filter=doc_filter,
            limit=limit,
        )

    def _dense(self, query: str, doc_filter: models.Filter, limit: int) -> models.Prefetch:
        return models.Prefetch(
            query=self.embedder.embed_query(query),
            using=DENSE,
            filter=doc_filter,
            limit=limit,
        )

    def _ensure_collection(self) -> None:
        if self.client.collection_exists(self.collection):
            return
        dense = (
            {
                DENSE: models.VectorParams(
                    size=self.embedder.dimension, distance=models.Distance.COSINE
                )
            }
            if self.embedder
            else {}
        )
        self.client.create_collection(
            self.collection,
            vectors_config=dense,
            sparse_vectors_config={
                LEXICAL: models.SparseVectorParams(modifier=models.Modifier.IDF)
            },
        )
        with warnings.catch_warnings():
            # Local mode has no payload indexes and says so; the server uses this one.
            warnings.simplefilter("ignore", UserWarning)
            self.client.create_payload_index(
                self.collection, "document_id", models.PayloadSchemaType.KEYWORD
            )


def _collection_name(embedder: Embedder | None) -> str:
    if embedder is None:
        return f"{COLLECTION}_lexical"
    slug = "".join(c if c.isalnum() else "_" for c in embedder.name.lower())
    return f"{COLLECTION}_{slug}"


def _only(document_id: str) -> models.Filter:
    return models.Filter(
        must=[models.FieldCondition(key="document_id", match=models.MatchValue(value=document_id))]
    )
