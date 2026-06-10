from __future__ import annotations

from typing import Any, Dict, List

from .config import ChunkBuilderConfig
from .utils import (
    ensure_dir,
    find_passage_package_dirs,
    read_jsonl,
    resolve_effective_to,
    write_json,
    write_jsonl,
)


class ChunkBuilder:
    def __init__(self, config: ChunkBuilderConfig):
        self.config = config

    def build_all(self) -> Dict[str, Any]:
        package_dirs = find_passage_package_dirs(self.config.passages_root)
        output_root = ensure_dir(self.config.output_root)
        summary: Dict[str, Any] = {
            "package_count": len(package_dirs),
            "total_chunks": 0,
            "skipped_non_atomic": 0,
            "skipped_empty_content": 0,
            "packages": {},
        }
        all_chunks: List[Dict[str, Any]] = []

        for package_dir in package_dirs:
            package_id = package_dir.name
            chunks, pkg_stats = self.build_package(package_dir)
            pkg_out = ensure_dir(output_root / package_id)
            write_jsonl(pkg_out / "chunks.jsonl", chunks)
            write_json(pkg_out / "chunk_summary.json", pkg_stats)
            summary["packages"][package_id] = pkg_stats
            summary["total_chunks"] += pkg_stats["chunk_count"]
            summary["skipped_non_atomic"] += pkg_stats["skipped_non_atomic"]
            summary["skipped_empty_content"] += pkg_stats["skipped_empty_content"]
            all_chunks.extend(chunks)

        write_jsonl(output_root / "all_chunks.jsonl", all_chunks)
        write_json(output_root / "chunk_summary.json", summary)
        return summary

    def build_package(self, package_dir) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
        passages_path = package_dir / "passages.jsonl"
        package_id = package_dir.name
        chunks: List[Dict[str, Any]] = []
        skipped_non_atomic = 0
        skipped_empty_content = 0

        for passage in read_jsonl(passages_path):
            if passage.get("passage_kind") != "atomic":
                skipped_non_atomic += 1
                continue

            content = (passage.get("content") or "").strip()
            if self.config.skip_empty_content and not content:
                skipped_empty_content += 1
                continue

            chunk = self._passage_to_chunk(passage, package_id)
            chunks.append(chunk)

        chunks.sort(key=lambda row: (
            str(row.get("package_id") or ""),
            str(row.get("path_text") or ""),
            str(row.get("chunk_id") or ""),
        ))
        stats = {
            "package_id": package_id,
            "chunk_count": len(chunks),
            "skipped_non_atomic": skipped_non_atomic,
            "skipped_empty_content": skipped_empty_content,
        }
        return chunks, stats

    @staticmethod
    def _passage_to_chunk(passage: Dict[str, Any], package_id: str) -> Dict[str, Any]:
        effective_from = passage.get("effective_from")
        if effective_from in {None, "", "null"}:
            effective_from = None

        return {
            "chunk_id": passage.get("passage_id"),
            "package_id": passage.get("package_id") or package_id,
            "document_number": passage.get("document_number"),
            "document_title": passage.get("document_title"),
            "path_text": passage.get("path_text"),
            "content": passage.get("content"),
            "effective_from": effective_from,
            "effective_to": resolve_effective_to(passage),
        }
