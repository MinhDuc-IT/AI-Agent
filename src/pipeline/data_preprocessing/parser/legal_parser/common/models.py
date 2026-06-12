from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

@dataclass
class ParserConfig:
    output_base_dir: Path = Path("./data/preprocessed/parsed")
    stop_at_appendix: bool = True
    stop_at_attachment_marker: bool = True
    write_tree_json: bool = True
    write_units_jsonl: bool = True
    normalize_tables: bool = True

@dataclass
class ParseResult:
    output_dir: Path
    tree_path: Path
    units_path: Path
    document_id: str
    node_count: int
    unit_count: int
    table_count: int
