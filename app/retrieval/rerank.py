"""Cross-encoder reranking.

Search returns candidates; a cross-encoder then reads the question and each
candidate together and scores how well the passage answers it. This is slower than
vector search, so it only runs on a short candidate list.
"""

from __future__ import annotations

from typing import Protocol

DEFAULT_RERANKER = "BAAI/bge-reranker-v2-m3-int8"


class Reranker(Protocol):
    name: str

    def score(self, query: str, texts: list[str]) -> list[float]: ...


class FastEmbedReranker:
    def __init__(self, model_name: str = DEFAULT_RERANKER, cache_dir: str | None = None) -> None:
        from fastembed.rerank.cross_encoder import TextCrossEncoder

        known = {m["model"] for m in TextCrossEncoder.list_supported_models()}
        if model_name not in known:
            raise ValueError(f"Unknown reranker model: {model_name}")
        self.name = model_name
        self._cache_dir = cache_dir
        self._model = None

    def score(self, query: str, texts: list[str]) -> list[float]:
        if self._model is None:
            from fastembed.rerank.cross_encoder import TextCrossEncoder

            self._model = TextCrossEncoder(self.name, cache_dir=self._cache_dir)
        return [float(s) for s in self._model.rerank(query, texts)]
