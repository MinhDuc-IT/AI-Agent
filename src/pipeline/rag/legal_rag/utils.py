from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List


def read_jsonl(path: Path) -> Iterator[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def load_chunks(chunks_path: Path, limit: int | None = None) -> List[Dict[str, Any]]:
    rows = list(iter_chunks(chunks_path))
    if limit is not None:
        return rows[:limit]
    return rows


def iter_chunks(chunks_path: Path) -> Iterable[Dict[str, Any]]:
    path = Path(chunks_path)
    if path.is_file():
        yield from read_jsonl(path)
        return
    if not path.exists():
        return
    global_file = path / "chunks.jsonl"
    if global_file.exists():
        yield from read_jsonl(global_file)
        return
    old_global_file = path / "all_chunks.jsonl"
    if old_global_file.exists():
        yield from read_jsonl(old_global_file)
        return
    for package_dir in sorted(p for p in path.iterdir() if p.is_dir()):
        chunk_file = package_dir / "chunks.jsonl"
        if chunk_file.exists():
            yield from read_jsonl(chunk_file)


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
