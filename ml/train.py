"""Trains the work category classifier and tracks every run in MLflow.

    python -m ml.train
    python -m ml.train --dim 128 --lr 0.005
    python -m ml.train --export          also copy the model to app/classify/model
    mlflow ui --backend-store-uri sqlite:///mlflow.db    compare runs at localhost:5000

Each run logs its parameters, validation macro-F1 per epoch, test metrics for the
model and for a keyword baseline, the confusion matrix, and the ONNX model. The
weights from the epoch with the best validation macro-F1 are kept (early stopping).
The test set holds only work items the model never saw in training.
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
import tempfile
from collections import Counter
from pathlib import Path

import mlflow
import numpy as np
import torch
from torch import nn

from app.classify.features import MAX_TOKENS, encode
from app.domain.enums import WorkCategory
from app.extraction.verify import CATEGORY_WORDS, category_in_quote
from ml.data import LABELS, Example, build
from ml.model import TenderCategoryModel

ROOT = Path(__file__).resolve().parent.parent
EXPORT_DIR = ROOT / "app" / "classify" / "model"


def tensors(examples: list[Example]) -> tuple[torch.Tensor, torch.Tensor]:
    ids = torch.tensor([encode(e.text) for e in examples], dtype=torch.long)
    labels = torch.tensor([LABELS.index(e.label) for e in examples], dtype=torch.long)
    return ids, labels


def metrics(true: list[int], pred: list[int]) -> dict[str, float]:
    f1s = []
    for c in range(len(LABELS)):
        tp = sum(1 for t, p in zip(true, pred, strict=True) if t == c and p == c)
        fp = sum(1 for t, p in zip(true, pred, strict=True) if t != c and p == c)
        fn = sum(1 for t, p in zip(true, pred, strict=True) if t == c and p != c)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1s.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    accuracy = sum(1 for t, p in zip(true, pred, strict=True) if t == p) / len(true)
    result = {"accuracy": accuracy, "macro_f1": sum(f1s) / len(f1s)}
    result.update({f"f1_{label}": f for label, f in zip(LABELS, f1s, strict=True)})
    return result


def confusion(true: list[int], pred: list[int]) -> list[list[int]]:
    matrix = [[0] * len(LABELS) for _ in LABELS]
    for t, p in zip(true, pred, strict=True):
        matrix[t][p] += 1
    return matrix


def keyword_baseline(text: str) -> int:
    """The category whose keywords appear most often; other works when none do."""
    hits = Counter(
        category
        for category in CATEGORY_WORDS
        for word in text.split()
        if category_in_quote(category, word)
    )
    if not hits:
        return LABELS.index(WorkCategory.OTHER_WORKS.value)
    return LABELS.index(hits.most_common(1)[0][0].value)


def predict(model: nn.Module, ids: torch.Tensor) -> list[int]:
    return probabilities(model, ids).argmax(dim=1).tolist()


def probabilities(model: nn.Module, ids: torch.Tensor) -> torch.Tensor:
    model.eval()
    with torch.no_grad():
        return torch.softmax(model(ids), dim=1)


def selective(probs: torch.Tensor, true: list[int], threshold: float) -> tuple[float, float]:
    """Share of examples above the confidence threshold, and accuracy on that share."""
    confidence, pred = probs.max(dim=1)
    kept = [i for i, c in enumerate(confidence.tolist()) if c >= threshold]
    if not kept:
        return 0.0, 0.0
    correct = sum(1 for i in kept if pred[i].item() == true[i])
    return len(kept) / len(true), correct / len(kept)


def export_onnx(model: nn.Module, path: Path) -> None:
    model.eval()
    sample = torch.zeros((1, MAX_TOKENS), dtype=torch.long)
    torch.onnx.export(
        model,
        (sample,),
        str(path),
        input_names=["ids"],
        output_names=["logits"],
        dynamic_axes={"ids": {0: "batch"}, "logits": {0: "batch"}},
        opset_version=17,
        dynamo=False,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dim", type=int, default=64)
    parser.add_argument("--dropout", type=float, default=0.5)
    parser.add_argument("--lr", type=float, default=0.003)
    parser.add_argument("--weight-decay", type=float, default=0.0001)
    parser.add_argument("--batch", type=int, default=32)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--patience", type=int, default=5)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--export", action="store_true", help="copy the model into the app")
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    data = build(seed=args.seed)
    x_train, y_train = tensors(data["train"])
    x_val, y_val = tensors(data["val"])
    x_test, y_test = tensors(data["test"])

    mlflow.set_experiment("tender-category")
    with mlflow.start_run():
        mlflow.log_params(vars(args) | {k: len(v) for k, v in data.items()})

        baseline = [keyword_baseline(e.text) for e in data["test"]]
        for name, value in metrics(y_test.tolist(), baseline).items():
            mlflow.log_metric(f"baseline_test_{name}", value)

        model = TenderCategoryModel(len(LABELS), args.dim, args.dropout)
        optimizer = torch.optim.AdamW(
            model.parameters(), lr=args.lr, weight_decay=args.weight_decay
        )
        loss_fn = nn.CrossEntropyLoss()
        best_f1, best_state, best_epoch, waited = -1.0, None, 0, 0

        for epoch in range(1, args.epochs + 1):
            model.train()
            order = torch.randperm(len(x_train))
            total = 0.0
            for start in range(0, len(order), args.batch):
                batch = order[start : start + args.batch]
                optimizer.zero_grad()
                loss = loss_fn(model(x_train[batch]), y_train[batch])
                loss.backward()
                optimizer.step()
                total += loss.item() * len(batch)

            val = metrics(y_val.tolist(), predict(model, x_val))
            mlflow.log_metric("train_loss", total / len(x_train), step=epoch)
            mlflow.log_metric("val_macro_f1", val["macro_f1"], step=epoch)
            print(
                f"epoch {epoch:>2}  loss {total / len(x_train):.4f}  val F1 {val['macro_f1']:.3f}"
            )

            if val["macro_f1"] > best_f1:
                best_f1, best_epoch, waited = val["macro_f1"], epoch, 0
                best_state = {k: v.clone() for k, v in model.state_dict().items()}
            else:
                waited += 1
                if waited >= args.patience:
                    break

        model.load_state_dict(best_state)
        mlflow.log_metric("best_epoch", best_epoch)
        test_probs = probabilities(model, x_test)
        test_pred = test_probs.argmax(dim=1).tolist()
        test = metrics(y_test.tolist(), test_pred)
        for name, value in test.items():
            mlflow.log_metric(f"test_{name}", value)
        thresholds = {t: selective(test_probs, y_test.tolist(), t) for t in (0.5, 0.7, 0.9)}
        for t, (coverage, accuracy) in thresholds.items():
            mlflow.log_metric(f"test_coverage_at_{t}", coverage)
            mlflow.log_metric(f"test_accuracy_at_{t}", accuracy)
        base = metrics(y_test.tolist(), baseline)

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            export_onnx(model, out / "category.onnx")
            (out / "labels.json").write_text(
                json.dumps({"labels": LABELS, "max_tokens": MAX_TOKENS}, indent=2),
                encoding="utf-8",
            )
            (out / "confusion.json").write_text(
                json.dumps({"labels": LABELS, "matrix": confusion(y_test.tolist(), test_pred)}),
                encoding="utf-8",
            )
            mlflow.log_artifacts(str(out))
            if args.export:
                EXPORT_DIR.mkdir(parents=True, exist_ok=True)
                for name in ("category.onnx", "labels.json"):
                    shutil.copy(out / name, EXPORT_DIR / name)

    print(f"\nbest epoch {best_epoch}")
    print(f"{'':<22}{'accuracy':>10}{'macro F1':>10}")
    print(f"{'keyword baseline':<22}{base['accuracy']:>10.1%}{base['macro_f1']:>10.3f}")
    print(f"{'model':<22}{test['accuracy']:>10.1%}{test['macro_f1']:>10.3f}")
    print("\nper class F1 (test)")
    for label in LABELS:
        print(f"  {label:<20}{test[f'f1_{label}']:.3f}   baseline {base[f'f1_{label}']:.3f}")
    print("\nconfidence  coverage  accuracy")
    for t, (coverage, accuracy) in thresholds.items():
        print(f"  >= {t:<7}{coverage:>9.1%}{accuracy:>10.1%}")
    if args.export:
        print(f"\nExported to {EXPORT_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
