from __future__ import annotations

import sys
from typing import List, Sequence

import torch
from fastembed import SparseTextEmbedding
from qdrant_client import models
from sentence_transformers import SentenceTransformer


def resolve_device(requested: str | None) -> str:
    device = (requested or "cpu").lower()
    if device != "cuda":
        return device
    if torch.cuda.is_available():
        return "cuda"
    print(
        "WARNING: --device cuda was requested but CUDA is unavailable "
        "(driver too old, missing GPU, or CPU-only PyTorch). Falling back to cpu.",
        file=sys.stderr,
    )
    return "cpu"


class ChunkEmbedder:
    def __init__(
        self,
        dense_model_name: str,
        sparse_model_name: str,
        device: str | None = None,
    ):
        self.device = resolve_device(device)
        try:
            self.dense_model = SentenceTransformer(dense_model_name, device=self.device)
        except RuntimeError as exc:
            if self.device != "cuda":
                raise
            print(f"WARNING: Failed to load model on cuda ({exc}). Falling back to cpu.", file=sys.stderr)
            self.device = "cpu"
            self.dense_model = SentenceTransformer(dense_model_name, device="cpu")
        self.dense_model.max_seq_length = 256
        self.sparse_model = SparseTextEmbedding(model_name=sparse_model_name)
        get_dim = getattr(self.dense_model, "get_embedding_dimension", None)
        if callable(get_dim):
            self.dense_size = int(get_dim())
        else:
            self.dense_size = int(self.dense_model.get_sentence_embedding_dimension())

    def embed_dense(self, texts: Sequence[str], *, batch_size: int = 32) -> List[List[float]]:
        vectors = self.dense_model.encode(
            list(texts),
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [vector.tolist() for vector in vectors]

    def embed_sparse(self, texts: Sequence[str]) -> List[models.SparseVector]:
        values = list(texts)
        sparse_vectors: List[models.SparseVector] = []
        for embedding in self.sparse_model.embed(values):
            sparse_vectors.append(
                models.SparseVector(
                    indices=embedding.indices.tolist(),
                    values=embedding.values.tolist(),
                )
            )
        return sparse_vectors
