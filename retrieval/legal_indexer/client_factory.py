from __future__ import annotations

from pathlib import Path

from qdrant_client import QdrantClient

from .config import IndexerConfig, SearcherConfig


def make_qdrant_client(config: IndexerConfig | SearcherConfig) -> QdrantClient:
    if config.qdrant_url:
        kwargs = {"url": config.qdrant_url}
        if config.qdrant_api_key:
            kwargs["api_key"] = config.qdrant_api_key
        return QdrantClient(**kwargs)

    path = Path(config.qdrant_path)
    path.mkdir(parents=True, exist_ok=True)
    return QdrantClient(path=str(path))
