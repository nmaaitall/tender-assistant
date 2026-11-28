"""Turns tender text into token ids for the category classifier.

Words are normalized like the lexical search (article and suffix removed). Each word
and each of its character trigrams is hashed into a fixed number of buckets, so
unseen words still share pieces with known ones (مضخات and مضخة share مضخ).
Training and serving use this same function.
"""

from __future__ import annotations

import zlib

from app.retrieval.sparse import terms

BUCKETS = 2**15
MAX_TOKENS = 256
PAD = 0


def _bucket(piece: str) -> int:
    # 0 is reserved for padding.
    return 1 + zlib.crc32(piece.encode("utf-8")) % (BUCKETS - 1)


def encode(text: str, max_tokens: int = MAX_TOKENS) -> list[int]:
    ids: list[int] = []
    for word in terms(text):
        ids.append(_bucket("w:" + word))
        marked = f"<{word}>"
        ids += [_bucket("c:" + marked[i : i + 3]) for i in range(len(marked) - 2)]
    ids = ids[:max_tokens]
    return ids + [PAD] * (max_tokens - len(ids))
