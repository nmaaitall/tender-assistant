from functools import lru_cache

from qdrant_client import QdrantClient

from app.config import settings
from app.retrieval.embeddings import FastEmbedEmbedder
from app.retrieval.index import ChunkIndex
from app.retrieval.rerank import FastEmbedReranker


@lru_cache
def get_index() -> ChunkIndex:
    if settings.qdrant_url:
        client = QdrantClient(url=settings.qdrant_url)
    else:
        client = QdrantClient(path=settings.qdrant_path)
    embedder = (
        FastEmbedEmbedder(settings.embedding_model, settings.model_cache_dir)
        if settings.embedding_model
        else None
    )
    reranker = (
        FastEmbedReranker(settings.reranker_model, settings.model_cache_dir)
        if settings.reranker_model
        else None
    )
    return ChunkIndex(client, embedder, reranker=reranker)
