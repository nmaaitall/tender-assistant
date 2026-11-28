"""Serves the trained category classifier with ONNX Runtime, so the API needs no
PyTorch. The model and its label list are produced by ml/train.py."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from pydantic import BaseModel

from app.classify.features import encode

MODEL_DIR = Path(__file__).resolve().parent / "model"


class CategoryPrediction(BaseModel):
    category: str
    confidence: float
    scores: dict[str, float]


class CategoryClassifier:
    def __init__(self, model_dir: Path = MODEL_DIR) -> None:
        import onnxruntime

        meta = json.loads((model_dir / "labels.json").read_text(encoding="utf-8"))
        self.labels: list[str] = meta["labels"]
        self.session = onnxruntime.InferenceSession(
            str(model_dir / "category.onnx"), providers=["CPUExecutionProvider"]
        )

    @classmethod
    def available(cls, model_dir: Path = MODEL_DIR) -> bool:
        return (model_dir / "category.onnx").exists()

    def predict(self, text: str) -> CategoryPrediction:
        ids = np.array([encode(text)], dtype=np.int64)
        (logits,) = self.session.run(None, {"ids": ids})
        exp = np.exp(logits[0] - logits[0].max())
        probs = exp / exp.sum()
        best = int(probs.argmax())
        return CategoryPrediction(
            category=self.labels[best],
            confidence=round(float(probs[best]), 4),
            scores={label: round(float(p), 4) for label, p in zip(self.labels, probs, strict=True)},
        )
