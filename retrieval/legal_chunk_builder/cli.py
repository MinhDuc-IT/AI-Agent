from __future__ import annotations

import argparse
from pathlib import Path

from .builder import ChunkBuilder
from .config import ChunkBuilderConfig


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Build retrieval chunks from atomic legal passages (step 1 of RAG pipeline)."
    )
    ap.add_argument(
        "--input",
        "-i",
        default="./data/preprocessed/passages",
        help="Passages root or one package folder containing passages.jsonl",
    )
    ap.add_argument(
        "--output",
        "-o",
        default="./data/preprocessed/chunks",
        help="Output folder for chunks.jsonl",
    )
    ap.add_argument(
        "--keep-empty-content",
        action="store_true",
        help="Keep atomic passages with empty content",
    )
    args = ap.parse_args()

    config = ChunkBuilderConfig(
        passages_root=Path(args.input),
        output_root=Path(args.output),
        skip_empty_content=not args.keep_empty_content,
    )
    summary = ChunkBuilder(config).build_all()

    print("Chunk building completed")
    print(f"Packages: {summary['package_count']}")
    print(f"Total chunks: {summary['total_chunks']}")
    print(f"Skipped non-atomic: {summary['skipped_non_atomic']}")
    print(f"Skipped empty content: {summary['skipped_empty_content']}")
    print(f"Output: {config.output_root}")


if __name__ == "__main__":
    main()
