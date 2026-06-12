from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAG_ROOT = PROJECT_ROOT / "src" / "pipeline" / "rag"
DEFAULT_QDRANT_PATH = PROJECT_ROOT / "data" / "preprocessed" / "qdrant"


def setup_retrieval_path() -> None:
    rag_root = str(RAG_ROOT)
    if rag_root not in sys.path:
        sys.path.insert(0, rag_root)
