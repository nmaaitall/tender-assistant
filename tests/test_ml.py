"""Training code tests. They need PyTorch (requirements-ml.txt) and skip without it."""

import pytest

torch = pytest.importorskip("torch")

from ml.data import LABELS, build  # noqa: E402
from ml.model import TenderCategoryModel  # noqa: E402
from ml.train import keyword_baseline, metrics, selective  # noqa: E402


def test_splits_share_no_work_item():
    data = build(per_class={"train": 40, "val": 10, "test": 10})
    first_lines = {split: {e.text.split("\n")[1] for e in ex} for split, ex in data.items()}
    assert not first_lines["train"] & first_lines["test"]


def test_model_output_shape():
    model = TenderCategoryModel(len(LABELS))
    ids = torch.zeros((3, 16), dtype=torch.long)
    ids[:, :4] = 5
    assert model(ids).shape == (3, len(LABELS))


def test_metrics():
    result = metrics([0, 0, 1, 1], [0, 1, 1, 1])
    assert result["accuracy"] == 0.75
    assert 0 < result["macro_f1"] < 1


def test_selective_accuracy():
    probs = torch.tensor([[0.9, 0.1], [0.6, 0.4], [0.2, 0.8]])
    coverage, accuracy = selective(probs, [0, 1, 1], 0.7)
    assert coverage == pytest.approx(2 / 3)
    assert accuracy == 1.0


def test_keyword_baseline():
    assert LABELS[keyword_baseline("تمديد خطوط مياه")] == "water_and_sewerage"
    assert LABELS[keyword_baseline("تنسيق حديقة")] == "other_works"
