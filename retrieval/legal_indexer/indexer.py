from __future__ import annotations

from typing import Any, Dict, List

from qdrant_client import models

from .client_factory import make_qdrant_client
from .config import IndexerConfig
from .qdrant_settings import qdrant_target_label
from .embedder import ChunkEmbedder
from .filters import chunk_payload
from .utils import build_chunk_text, load_chunks, point_id_for_chunk


class ChunkIndexer:
    def __init__(self, config: IndexerConfig):
        self.config = config
        self.client = make_qdrant_client(config)
        self.embedder = ChunkEmbedder(
            dense_model_name=config.dense_model_name,
            sparse_model_name=config.sparse_model_name,
            device=config.device,
        )

    def run(self) -> Dict[str, Any]:
        chunks = load_chunks(self.config.chunks_root, limit=self.config.limit)
        if not chunks:
            raise FileNotFoundError(f"No chunks found under: {self.config.chunks_root}")

        self._ensure_collection(recreate=self.config.recreate_collection)

        indexed = 0
        batch_size = max(1, self.config.batch_size)
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start:start + batch_size]
            texts = [build_chunk_text(chunk) for chunk in batch]
            dense_vectors = self.embedder.embed_dense(texts)
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
                            "dense": dense_vector,
                            "sparse": sparse_vector,
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
        }

    def _ensure_collection(self, recreate: bool) -> None:
        if recreate and self.client.collection_exists(self.config.collection_name):
            self.client.delete_collection(self.config.collection_name)

        if self.client.collection_exists(self.config.collection_name):
            return

        self.client.create_collection(
            collection_name=self.config.collection_name,
            vectors_config={
                "dense": models.VectorParams(
                    size=self.embedder.dense_size,
                    distance=models.Distance.COSINE,
                ),
            },
            sparse_vectors_config={
                "sparse": models.SparseVectorParams(
                    modifier=models.Modifier.IDF,
                ),
            },
        )
        self.client.create_payload_index(
            collection_name=self.config.collection_name,
            field_name="document_number",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )
        self.client.create_payload_index(
            collection_name=self.config.collection_name,
            field_name="effective_from_int",
            field_schema=models.PayloadSchemaType.INTEGER,
        )
        self.client.create_payload_index(
            collection_name=self.config.collection_name,
            field_name="effective_to_int",
            field_schema=models.PayloadSchemaType.INTEGER,
        )
        self.client.create_payload_index(
            collection_name=self.config.collection_name,
            field_name="package_id",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )
