from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class IndexerConfig:
    chunks_root: Path = Path("../data/preprocessed/chunks")
    qdrant_path: Path = Path("../data/preprocessed/qdrant")
    qdrant_url: str | None = None
    qdrant_api_key: str | None = None
    collection_name: str = "legal_chunks"
    dense_model_name: str = "bkai-foundation-models/vietnamese-bi-encoder"
    sparse_model_name: str = "Qdrant/bm25"
    batch_size: int = 32
    device: str | None = None
    recreate_collection: bool = False
    limit: int | None = None


@dataclass
class SearcherConfig:
    qdrant_path: Path = Path("../data/preprocessed/qdrant")
    qdrant_url: str | None = None
    qdrant_api_key: str | None = None
    collection_name: str = "legal_chunks"
    dense_model_name: str = "bkai-foundation-models/vietnamese-bi-encoder"
    sparse_model_name: str = "Qdrant/bm25"
    device: str | None = None
    prefetch_limit: int = 20
    top_k: int = 5
