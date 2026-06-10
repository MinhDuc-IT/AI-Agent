from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Dict, Iterator, List


def read_jsonl(path: Path) -> Iterator[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def load_chunks(chunks_root: Path, limit: int | None = None) -> List[Dict[str, Any]]:
    root = Path(chunks_root)
    all_file = root / "all_chunks.jsonl"
    if all_file.exists():
        rows = list(read_jsonl(all_file))
    else:
        rows = []
        for package_dir in sorted(p for p in root.iterdir() if p.is_dir()):
            chunk_file = package_dir / "chunks.jsonl"
            if chunk_file.exists():
                rows.extend(read_jsonl(chunk_file))
    if limit is not None:
        return rows[:limit]
    return rows


def build_chunk_text(chunk: Dict[str, Any]) -> str:
    parts: List[str] = []
    document_number = (chunk.get("document_number") or "").strip()
    path_text = (chunk.get("path_text") or "").strip()
    content = (chunk.get("content") or "").strip()
    if document_number:
        parts.append(document_number)
    if path_text:
        parts.append(path_text)
    if content:
        parts.append(content)
    return "\n".join(parts)


def point_id_for_chunk(chunk_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id or "unknown"))
