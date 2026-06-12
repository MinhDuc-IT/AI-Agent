from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict


@dataclass
class ChunkerConfig:
    parsed_input_dir: Path = Path("./data/preprocessed/parsed")
    effectivity_dir: Path = Path("./data/preprocessed/effectivity")
    output_dir: Path = Path("./data/preprocessed/chunks")
    max_chars_per_chunk: int = 3000
    mode: str = "clause_if_long"
    write_package_chunks: bool = True


@dataclass
class ChunkBuildResult:
    output_dir: Path
    chunks_path: Path
    manifest_path: Path
    package_count: int
    chunk_count: int
    package_chunk_counts: Dict[str, int] = field(default_factory=dict)
