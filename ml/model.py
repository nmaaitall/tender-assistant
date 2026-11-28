import torch
from torch import nn

from app.classify.features import BUCKETS, PAD


class TenderCategoryModel(nn.Module):
    """Hashed word and character-trigram embeddings, averaged, then a linear layer.

    Small on purpose: about two million parameters, trains in seconds on a CPU, and
    exports to ONNX for serving without PyTorch.
    """

    def __init__(self, n_classes: int, dim: int = 64, dropout: float = 0.2) -> None:
        super().__init__()
        self.embedding = nn.Embedding(BUCKETS, dim, padding_idx=PAD)
        self.dropout = nn.Dropout(dropout)
        self.out = nn.Linear(dim, n_classes)

    def forward(self, ids: torch.Tensor) -> torch.Tensor:
        mask = (ids != PAD).unsqueeze(-1).float()
        summed = (self.embedding(ids) * mask).sum(dim=1)
        mean = summed / mask.sum(dim=1).clamp(min=1.0)
        return self.out(self.dropout(mean))
