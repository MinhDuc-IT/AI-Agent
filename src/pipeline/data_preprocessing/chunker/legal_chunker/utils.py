from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Union


def collapse_ws(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text or "")).strip()


def strip_vietnamese_accents(text: str, keep_dd: bool = False) -> str:
    if keep_dd:
        text = text.replace("đ", "dd").replace("Đ", "dd")
    else:
        text = text.replace("đ", "d").replace("Đ", "D")
    return unicodedata.normalize("NFKD", text or "").encode("ASCII", "ignore").decode("utf-8")


def normalize_id(text: str) -> str:
    text = strip_vietnamese_accents(text or "", keep_dd=True)
    text = text.replace("/", "_").replace("-", "_")
    text = re.sub(r"\s+", "_", text).lower()
    text = re.sub(r"[^a-z0-9_\.]", "", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "unknown"


def md5_text(text: str) -> str:
    return hashlib.md5((text or "").encode("utf-8")).hexdigest()


def ensure_dir(path: Union[str, Path]) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def read_json(path: Union[str, Path]) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Union[str, Path], data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def read_jsonl(path: Union[str, Path]) -> Iterator[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def write_jsonl(path: Union[str, Path], rows: Iterable[Dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def common_path_text(paths: Iterable[str]) -> str:
    split_paths: List[List[str]] = []
    for path in paths:
        parts = [collapse_ws(part) for part in (path or "").split(" > ") if collapse_ws(part)]
        if parts:
            split_paths.append(parts)
    if not split_paths:
        return ""
    common = list(split_paths[0])
    for parts in split_paths[1:]:
        limit = min(len(common), len(parts))
        idx = 0
        while idx < limit and common[idx] == parts[idx]:
            idx += 1
        common = common[:idx]
        if not common:
            break
    return " > ".join(common) if common else split_paths[0][0]


def prefixed_path_text(document_number: Optional[str], path_text: str) -> str:
    path_text = collapse_ws(path_text)
    doc_no = collapse_ws(document_number or "")
    if not doc_no or doc_no == "UNKNOWN":
        return path_text
    if path_text == doc_no or path_text.startswith(doc_no + " > "):
        return path_text
    return f"{doc_no} > {path_text}" if path_text else doc_no


def compact_path_text(path_text: str, *, max_part_chars: int = 240, max_total_chars: int = 1400) -> str:
    parts = [collapse_ws(part) for part in (path_text or "").split(" > ") if collapse_ws(part)]
    compacted = [_compact_path_part(part, max_part_chars=max_part_chars) for part in parts]
    out = " > ".join(compacted)
    if len(out) <= max_total_chars:
        return out
    compacted = [_compact_path_part(part, max_part_chars=120) for part in compacted]
    out = " > ".join(compacted)
    if len(out) <= max_total_chars:
        return out
    keep: List[str] = []
    total = 0
    for part in compacted:
        next_total = total + len(part) + (3 if keep else 0)
        if keep and next_total > max_total_chars:
            keep.append("...")
            break
        keep.append(part)
        total = next_total
    return " > ".join(keep)


def _compact_path_part(part: str, *, max_part_chars: int) -> str:
    quote_match = re.match(r"^(Đoạn trích\s+\S+)\.?\s+.+$", part, flags=re.IGNORECASE | re.UNICODE)
    if quote_match:
        return quote_match.group(1)
    if len(part) <= max_part_chars:
        return part
    cut = part[:max_part_chars].rstrip()
    space = cut.rfind(" ")
    if space >= int(max_part_chars * 0.7):
        cut = cut[:space].rstrip()
    return cut + "..."
