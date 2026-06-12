from __future__ import annotations

from typing import Any, Dict, List, Optional

from qdrant_client import models

from .client_factory import make_qdrant_client
from .config import RetrievalMode, RetrieveConfig
from .embedder import ChunkEmbedder
from .filters import build_retrieval_filter
from .store import QdrantChunkStore


class ChunkRetriever:
    def __init__(self, config: RetrieveConfig):
        self.config = config
        self.client = make_qdrant_client(config)
        self.store = QdrantChunkStore(self.client, config)
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
        mode: Optional[RetrievalMode] = None,
        top_k: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        return self.retrieve(
            query,
            as_of_date=as_of_date,
            document_number=document_number,
            mode=mode,
            top_k=top_k,
        )

    def retrieve(
        self,
        query: str,
        *,
        as_of_date: Optional[str] = None,
        document_number: Optional[str] = None,
        mode: Optional[RetrievalMode] = None,
        top_k: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        if not self.store.collection_exists():
            raise FileNotFoundError(
                f"Collection not found: {self.config.collection_name}. Run rag/index_chunks.py first."
            )

        retrieval_mode = mode or self.config.mode
        limit = top_k or self.config.top_k
        prefetch_limit = max(limit, self.config.prefetch_limit)
        query_filter = build_retrieval_filter(as_of_date=as_of_date, document_number=document_number)

        response = self._query_points(
            query=query,
            mode=retrieval_mode,
            query_filter=query_filter,
            limit=limit,
            prefetch_limit=prefetch_limit,
        )

        results: List[Dict[str, Any]] = []
        for point in response.points:
            payload = point.payload or {}
            results.append({
                "score": point.score,
                "mode": retrieval_mode,
                "chunk_id": payload.get("chunk_id"),
                "source_unit_ids": payload.get("source_unit_ids") or [],
                "document_number": payload.get("document_number"),
                "document_title": payload.get("document_title"),
                "document_type": payload.get("document_type"),
                "path_text": payload.get("path_text"),
                "content": payload.get("content"),
                "effective_from": payload.get("effective_from"),
                "effective_to": payload.get("effective_to"),
                "source_file": payload.get("source_file"),
                "source_url": payload.get("source_url"),
            })
        return results

    def _query_points(
        self,
        *,
        query: str,
        mode: RetrievalMode,
        query_filter: Optional[models.Filter],
        limit: int,
        prefetch_limit: int,
    ):
        if mode == "dense":
            dense_vector = self.embedder.embed_dense([query])[0]
            return self.client.query_points(
                collection_name=self.config.collection_name,
                query=dense_vector,
                using=self.config.dense_vector_name,
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
            )
        if mode == "sparse":
            sparse_vector = self.embedder.embed_sparse([query])[0]
            return self.client.query_points(
                collection_name=self.config.collection_name,
                query=sparse_vector,
                using=self.config.sparse_vector_name,
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
            )
        if mode != "hybrid":
            raise ValueError(f"Unsupported retrieval mode: {mode}")

        dense_vector = self.embedder.embed_dense([query])[0]
        sparse_vector = self.embedder.embed_sparse([query])[0]
        return self.client.query_points(
            collection_name=self.config.collection_name,
            prefetch=[
                models.Prefetch(
                    query=sparse_vector,
                    using=self.config.sparse_vector_name,
                    filter=query_filter,
                    limit=prefetch_limit,
                ),
                models.Prefetch(
                    query=dense_vector,
                    using=self.config.dense_vector_name,
                    filter=query_filter,
                    limit=prefetch_limit,
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
        )


ChunkSearcher = ChunkRetriever
