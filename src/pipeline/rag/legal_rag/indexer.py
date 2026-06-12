from __future__ import annotations

from typing import Any, Dict, List

from qdrant_client import models

from .client_factory import make_qdrant_client
from .config import IndexConfig
from .qdrant_settings import qdrant_target_label
from .embedder import ChunkEmbedder
from .filters import chunk_payload
from .store import QdrantChunkStore
from .utils import build_chunk_text, load_chunks, point_id_for_chunk


class ChunkIndexer:
    def __init__(self, config: IndexConfig):
        self.config = config
        self.client = make_qdrant_client(config)
        self.store = QdrantChunkStore(self.client, config)
        self.embedder = ChunkEmbedder(
            dense_model_name=config.dense_model_name,
            sparse_model_name=config.sparse_model_name,
            device=config.device,
        )

    def run(self) -> Dict[str, Any]:
        chunks = load_chunks(self.config.chunks_path, limit=self.config.limit)
        if not chunks:
            raise FileNotFoundError(f"No chunks found from: {self.config.chunks_path}")

        self.store.ensure_collection(
            dense_size=self.embedder.dense_size,
            recreate=self.config.recreate_collection,
        )

        indexed = 0
        batch_size = max(1, self.config.batch_size)
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start:start + batch_size]
            texts = [build_chunk_text(chunk) for chunk in batch]
            dense_vectors = self.embedder.embed_dense(texts, batch_size=batch_size)
            sparse_vectors = self.embedder.embed_sparse(texts)

            points = []
            for chunk, text, dense_vector, sparse_vector in zip(
                batch, texts, dense_vectors, sparse_vectors, strict=True
            ):
                chunk_id = str(chunk.get("chunk_id") or "")
                points.append(
                    models.PointStruct(
                        id=point_id_for_chunk(chunk_id),
                        vector={
                            self.config.dense_vector_name: dense_vector,
                            self.config.sparse_vector_name: sparse_vector,
                        },
                        payload=chunk_payload(chunk, text),
                    )
                )

            self.client.upsert(
                collection_name=self.config.collection_name,
                points=points,
                wait=True,
            )
            indexed += len(points)
            print(f"Indexed {indexed}/{len(chunks)} chunks")

        return {
            "collection_name": self.config.collection_name,
            "indexed_chunks": indexed,
            "qdrant_target": qdrant_target_label(self.config),
            "dense_model": self.config.dense_model_name,
            "sparse_model": self.config.sparse_model_name,
            "payload_indexes": ["document_number", "effective_from_int", "effective_to_int"],
        }
