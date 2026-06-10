from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from legal_indexer.config import SearcherConfig
from legal_indexer.qdrant_settings import apply_qdrant_settings, qdrant_target_label

from .config import GeneratorConfig
from .generator import LegalQAGenerator


def _configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


def main() -> None:
    _configure_stdout()
    ap = argparse.ArgumentParser(
        description="Retrieve legal chunks and generate an answer with OpenRouter."
    )
    ap.add_argument("query", help="User question")
    ap.add_argument("--qdrant-path", default="../data/preprocessed/qdrant")
    ap.add_argument("--qdrant-url", default=None)
    ap.add_argument("--qdrant-api-key", default=None)
    ap.add_argument("--local-qdrant", action="store_true")
    ap.add_argument("--collection", default="legal_chunks")
    ap.add_argument("--dense-model", default="bkai-foundation-models/vietnamese-bi-encoder")
    ap.add_argument("--sparse-model", default="Qdrant/bm25")
    ap.add_argument("--device", default=None)
    ap.add_argument("--as-of", dest="as_of", default=None, help="Filter by effectivity date (YYYY-MM-DD)")
    ap.add_argument("--document-number", default=None)
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--model", default="openai/gpt-4o-mini", help="OpenRouter model id")
    ap.add_argument("--max-tokens", type=int, default=1024)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--json", action="store_true", help="Print raw JSON result")
    ap.add_argument("--no-sources", action="store_true", help="Hide retrieved source chunks")
    args = ap.parse_args()

    searcher_config = SearcherConfig(
        qdrant_path=Path(args.qdrant_path),
        collection_name=args.collection,
        dense_model_name=args.dense_model,
        sparse_model_name=args.sparse_model,
        device=args.device,
        top_k=args.top,
    )
    apply_qdrant_settings(
        searcher_config,
        qdrant_url=args.qdrant_url,
        qdrant_api_key=args.qdrant_api_key,
        use_local=args.local_qdrant,
    )
    generator_config = GeneratorConfig(
        model=args.model,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
    )

    print(f"Qdrant target: {qdrant_target_label(searcher_config)}")
    print(f"LLM model: {generator_config.model}")
    result = LegalQAGenerator(searcher_config, generator_config).ask(
        args.query,
        as_of_date=args.as_of,
        document_number=args.document_number,
        top_k=args.top,
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print(f"\nCâu hỏi: {result['query']}")
    if result.get("as_of"):
        print(f"Ngày tra cứu: {result['as_of']}")
    if result.get("document_number"):
        print(f"Văn bản lọc: {result['document_number']}")
    print("-" * 60)
    print("Trả lời:")
    print(result["answer"])

    if not args.no_sources:
        print("\n" + "-" * 60)
        print("Nguồn truy xuất:")
        for idx, row in enumerate(result["sources"], start=1):
            print(f"\n[{idx}] score={row.get('score'):.4f} | {row.get('document_number')}")
            print(f"    {row.get('path_text')}")
            content = (row.get("content") or "").strip()
            if len(content) > 200:
                content = content[:200] + "..."
            print(f"    {content}")


if __name__ == "__main__":
    main()
