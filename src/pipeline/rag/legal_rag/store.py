from __future__ import annotations

from typing import Iterable, Tuple

from qdrant_client import QdrantClient, models

from .config import RagConfig
from .filters import PAYLOAD_INDEX_FIELDS


class QdrantChunkStore:
    def __init__(self, client: QdrantClient, config: RagConfig):
        self.client = client
        self.config = config

    def collection_exists(self) -> bool:
        return self.client.collection_exists(self.config.collection_name)

    def ensure_collection(self, *, dense_size: int, recreate: bool = False) -> None:
        if recreate and self.collection_exists():
            self.client.delete_collection(self.config.collection_name)

        if not self.collection_exists():
            self.client.create_collection(
                collection_name=self.config.collection_name,
                vectors_config={
                    self.config.dense_vector_name: models.VectorParams(
                        size=dense_size,
                        distance=models.Distance.COSINE,
                    ),
                },
                sparse_vectors_config={
                    self.config.sparse_vector_name: models.SparseVectorParams(
                        modifier=models.Modifier.IDF,
                    ),
                },
            )

        self.ensure_payload_indexes(PAYLOAD_INDEX_FIELDS)

    def ensure_payload_indexes(
        self,
        fields: Iterable[Tuple[str, models.PayloadSchemaType]],
    ) -> None:
        for field_name, field_schema in fields:
            try:
                self.client.create_payload_index(
                    collection_name=self.config.collection_name,
                    field_name=field_name,
                    field_schema=field_schema,
                )
            except Exception as exc:
                message = str(exc).lower()
                if "already exists" not in message and "index exists" not in message:
                    raise
