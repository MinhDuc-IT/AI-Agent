from __future__ import annotations

import argparse
from pathlib import Path

from .builder import LegalChunkBuilder
from .models import ChunkerConfig


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build minimal RAG chunks from parsed legal trees.")
    parser.add_argument("--input", default="data/preprocessed/parsed", help="Parsed package directory or parsed dataset root.")
    parser.add_argument("--effectivity", default="data/preprocessed/effectivity", help="Effectivity output directory.")
    parser.add_argument("--output", default="data/preprocessed/chunks", help="Chunk output directory.")
    parser.add_argument("--max-chars", type=int, default=3000, help="Maximum characters per chunk before splitting.")
    parser.add_argument(
        "--mode",
        choices=["article", "clause_if_long"],
        default="clause_if_long",
        help="Chunk mode for main legal documents.",
    )
    parser.add_argument("--no-package-files", action="store_true", help="Only write the global chunks.jsonl.")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    config = ChunkerConfig(
        parsed_input_dir=Path(args.input),
        effectivity_dir=Path(args.effectivity),
        output_dir=Path(args.output),
        max_chars_per_chunk=args.max_chars,
        mode=args.mode,
        write_package_chunks=not args.no_package_files,
    )
    builder = LegalChunkBuilder(config)
    result = builder.build_dataset()
    print(f"Packages: {result.package_count}")
    print(f"Chunks: {result.chunk_count}")
    print(f"Chunks file: {result.chunks_path}")
    print(f"Manifest: {result.manifest_path}")
