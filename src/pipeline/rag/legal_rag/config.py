from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

RetrievalMode = Literal["dense", "sparse", "hybrid"]


@dataclass
class RagConfig:
    qdrant_path: Path = Path("data/preprocessed/qdrant")
    qdrant_url: Optional[str] = None
    qdrant_api_key: Optional[str] = None
    collection_name: str = "legal_chunks"
    dense_model_name: str = "bkai-foundation-models/vietnamese-bi-encoder"
    sparse_model_name: str = "Qdrant/bm25"
    dense_vector_name: str = "dense"
    sparse_vector_name: str = "sparse"
    device: Optional[str] = None


@dataclass
class IndexConfig(RagConfig):
    chunks_path: Path = Path("data/preprocessed/chunks/chunks.jsonl")
    batch_size: int = 32
    recreate_collection: bool = False
    limit: Optional[int] = None


@dataclass
class RetrieveConfig(RagConfig):
    mode: RetrievalMode = "hybrid"
    prefetch_limit: int = 30
    top_k: int = 5
