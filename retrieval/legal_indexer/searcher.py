from __future__ import annotations

from typing import Any, Dict, List, Optional

from qdrant_client import models

from .client_factory import make_qdrant_client
from .config import SearcherConfig
from .embedder import ChunkEmbedder
from .filters import build_query_filter
from .utils import build_chunk_text


class ChunkSearcher:
    def __init__(self, config: SearcherConfig):
        self.config = config
        self.client = make_qdrant_client(config)
        self.embedder = ChunkEmbedder(
            dense_model_name=config.dense_model_name,
            sparse_model_name=config.sparse_model_name,
            device=config.device,
        )

    def search(
        self,
        query: str,
        *,
        as_of_date: Optional[str] = None,
        document_number: Optional[str] = None,
        top_k: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        if not self.client.collection_exists(self.config.collection_name):
            raise FileNotFoundError(
                f"Collection not found: {self.config.collection_name}. Run index_chunks.py first."
            )

        limit = top_k or self.config.top_k
        prefetch_limit = max(limit, self.config.prefetch_limit)
        query_filter = build_query_filter(as_of_date=as_of_date, document_number=document_number)

        dense_vector = self.embedder.embed_dense([query])[0]
        sparse_vector = self.embedder.embed_sparse([query])[0]

        response = self.client.query_points(
            collection_name=self.config.collection_name,
            prefetch=[
                models.Prefetch(
                    query=sparse_vector,
                    using="sparse",
                    filter=query_filter,
                    limit=prefetch_limit,
                ),
                models.Prefetch(
                    query=dense_vector,
                    using="dense",
                    filter=query_filter,
                    limit=prefetch_limit,
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
        )

        results: List[Dict[str, Any]] = []
        for point in response.points:
            payload = point.payload or {}
            results.append({
                "score": point.score,
                "chunk_id": payload.get("chunk_id"),
                "package_id": payload.get("package_id"),
                "document_number": payload.get("document_number"),
                "document_title": payload.get("document_title"),
                "path_text": payload.get("path_text"),
                "content": payload.get("content"),
                "effective_from": payload.get("effective_from"),
                "effective_to": payload.get("effective_to"),
            })
        return results
