from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import SearcherConfig
from .qdrant_settings import apply_qdrant_settings, qdrant_target_label
from .searcher import ChunkSearcher


def _configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


def main() -> None:
    _configure_stdout()
    ap = argparse.ArgumentParser(description="Hybrid search legal chunks (BM25 + dense), return top-k.")
    ap.add_argument("query", help="Search query")
    ap.add_argument("--qdrant-path", default="../data/preprocessed/qdrant")
    ap.add_argument("--qdrant-url", default=None, help="Qdrant Cloud URL (default: QDRANT_URL from .env)")
    ap.add_argument("--qdrant-api-key", default=None, help="Qdrant API key (default: QDRANT_API_KEY from .env)")
    ap.add_argument("--local-qdrant", action="store_true", help="Use local Qdrant path instead of cloud .env")
    ap.add_argument("--collection", default="legal_chunks")
    ap.add_argument("--dense-model", default="bkai-foundation-models/vietnamese-bi-encoder")
    ap.add_argument("--sparse-model", default="Qdrant/bm25")
    ap.add_argument("--device", default=None)
    ap.add_argument("--as-of", dest="as_of", default=None, help="Filter by effectivity date (YYYY-MM-DD)")
    ap.add_argument("--document-number", default=None, help='Filter by document number, e.g. "119/2021/ND-CP"')
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--json", action="store_true", help="Print raw JSON results")
    args = ap.parse_args()

    config = SearcherConfig(
        qdrant_path=Path(args.qdrant_path),
        collection_name=args.collection,
        dense_model_name=args.dense_model,
        sparse_model_name=args.sparse_model,
        device=args.device,
        top_k=args.top,
    )
    apply_qdrant_settings(
        config,
        qdrant_url=args.qdrant_url,
        qdrant_api_key=args.qdrant_api_key,
        use_local=args.local_qdrant,
    )
    print(f"Qdrant target: {qdrant_target_label(config)}")
    results = ChunkSearcher(config).search(
        args.query,
        as_of_date=args.as_of,
        document_number=args.document_number,
        top_k=args.top,
    )

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    print(f"Query: {args.query}")
    if args.as_of:
        print(f"As of: {args.as_of}")
    if args.document_number:
        print(f"Document: {args.document_number}")
    print("-" * 60)
    for idx, row in enumerate(results, start=1):
        print(f"[{idx}] score={row.get('score'):.4f}")
        print(f"    chunk_id: {row.get('chunk_id')}")
        print(f"    document_number: {row.get('document_number')}")
        print(f"    path_text: {row.get('path_text')}")
        print(f"    effective_from: {row.get('effective_from')} | effective_to: {row.get('effective_to')}")
        content = (row.get("content") or "").strip()
        if len(content) > 240:
            content = content[:240] + "..."
        print(f"    content: {content}")
        print()


if __name__ == "__main__":
    main()
