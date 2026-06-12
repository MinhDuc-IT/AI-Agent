from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import IndexConfig
from .qdrant_settings import apply_qdrant_settings, qdrant_target_label


def _configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


def main() -> None:
    _configure_stdout()
    ap = argparse.ArgumentParser(description="Embed legal chunks and index them into Qdrant.")
    ap.add_argument("--chunks", "-i", default="data/preprocessed/chunks/chunks.jsonl", help="Global chunks.jsonl file or chunks directory.")
    ap.add_argument("--qdrant-path", default="data/preprocessed/qdrant")
    ap.add_argument("--qdrant-url", default=None, help="Qdrant Cloud URL (default: QDRANT_URL from .env)")
    ap.add_argument("--qdrant-api-key", default=None, help="Qdrant API key (default: QDRANT_API_KEY from .env)")
    ap.add_argument("--local-qdrant", action="store_true", help="Use local Qdrant path instead of cloud .env")
    ap.add_argument("--collection", default="legal_chunks")
    ap.add_argument("--dense-model", default="bkai-foundation-models/vietnamese-bi-encoder")
    ap.add_argument("--sparse-model", default="Qdrant/bm25")
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--device", default=None, help="cpu or cuda")
    ap.add_argument("--recreate", action="store_true", help="Drop and recreate the collection")
    ap.add_argument("--limit", type=int, default=None, help="Index only the first N chunks (for testing)")
    args = ap.parse_args()

    config = IndexConfig(
        chunks_path=Path(args.chunks),
        qdrant_path=Path(args.qdrant_path),
        collection_name=args.collection,
        dense_model_name=args.dense_model,
        sparse_model_name=args.sparse_model,
        batch_size=args.batch_size,
        device=args.device,
        recreate_collection=args.recreate,
        limit=args.limit,
    )
    apply_qdrant_settings(
        config,
        qdrant_url=args.qdrant_url,
        qdrant_api_key=args.qdrant_api_key,
        use_local=args.local_qdrant,
    )
    print(f"Qdrant target: {qdrant_target_label(config)}")
    from .indexer import ChunkIndexer

    summary = ChunkIndexer(config).run()
    print("Indexing completed")
    for key, value in summary.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
