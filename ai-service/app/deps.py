from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from .retrieval_path import DEFAULT_QDRANT_PATH, setup_pipeline_path

setup_pipeline_path()

from src.pipeline.agents.answer_agent import AnswerAgent  # noqa: E402
from src.pipeline.rag.legal_rag.config import RetrieveConfig  # noqa: E402
from src.pipeline.rag.legal_rag.qdrant_settings import apply_qdrant_settings, qdrant_target_label  # noqa: E402
from src.pipeline.rag.legal_rag.retriever import ChunkRetriever  # noqa: E402


@dataclass
class AppState:
    retriever: ChunkRetriever
    answer_agent: AnswerAgent
    qdrant_target: str
    model: str
    max_tokens: int
    temperature: float


@dataclass
class ServiceConfig:
    qdrant_path: Path = field(default_factory=lambda: DEFAULT_QDRANT_PATH)
    qdrant_url: Optional[str] = None
    qdrant_api_key: Optional[str] = None
    use_local_qdrant: bool = False
    collection: str = "legal_chunks"
    dense_model: str = "bkai-foundation-models/vietnamese-bi-encoder"
    sparse_model: str = "Qdrant/bm25"
    device: Optional[str] = None
    top_k: int = 5
    llm_model: str = "openai/gpt-4o-mini"
    max_tokens: int = 1024
    temperature: float = 0.0
    cors_origins: List[str] = field(default_factory=lambda: [
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ])


def build_app_state(config: ServiceConfig) -> AppState:
    retriever_config = RetrieveConfig(
        qdrant_path=config.qdrant_path,
        collection_name=config.collection,
        dense_model_name=config.dense_model,
        sparse_model_name=config.sparse_model,
        device=config.device,
        top_k=config.top_k,
    )
    apply_qdrant_settings(
        retriever_config,
        qdrant_url=config.qdrant_url,
        qdrant_api_key=config.qdrant_api_key,
        use_local=config.use_local_qdrant,
    )
    retriever = ChunkRetriever(retriever_config)
    answer_agent = AnswerAgent()
    return AppState(
        retriever=retriever,
        answer_agent=answer_agent,
        qdrant_target=qdrant_target_label(retriever_config),
        model=config.llm_model,
        max_tokens=config.max_tokens,
        temperature=config.temperature,
    )
