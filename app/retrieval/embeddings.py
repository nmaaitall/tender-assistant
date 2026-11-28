"""Dense sentence embeddings.

Models run on CPU through ONNX (fastembed), so no GPU or PyTorch is needed. They
are downloaded on first use. Several models expect a prefix that tells a question
from a passage; those prefixes are added here.
"""

from __future__ import annotations

from typing import Protocol

DEFAULT_MODEL = "google/embeddinggemma-300m"

# Model -> (query prefix, passage prefix), as given in each model card.
PREFIXES = {
    "intfloat/multilingual-e5-large": ("query: ", "passage: "),
    "google/embeddinggemma-300m": ("task: search result | query: ", "title: none | text: "),
    "Qwen/Qwen3-Embedding-0.6B-Q": (
        "Instruct: Given a question about a tender, find the passage that answers it\nQuery:",
        "",
    ),
}


class Embedder(Protocol):
    name: str
    dimension: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class FastEmbedEmbedder:
    def __init__(self, model_name: str = DEFAULT_MODEL, cache_dir: str | None = None) -> None:
        from fastembed import TextEmbedding

        known = {m["model"]: m["dim"] for m in TextEmbedding.list_supported_models()}
        if model_name not in known:
            raise ValueError(f"Unknown embedding model: {model_name}")
        self.name = model_name
        self.dimension = known[model_name]
        self._query_prefix, self._passage_prefix = PREFIXES.get(model_name, ("", ""))
        self._cache_dir = cache_dir
        self._model = None

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed([self._passage_prefix + t for t in texts])

    def embed_query(self, text: str) -> list[float]:
        return self._embed([self._query_prefix + text])[0]

    def _embed(self, texts: list[str]) -> list[list[float]]:
        if self._model is None:
            from fastembed import TextEmbedding

            self._model = TextEmbedding(self.name, cache_dir=self._cache_dir)
        return [vector.tolist() for vector in self._model.embed(texts)]
