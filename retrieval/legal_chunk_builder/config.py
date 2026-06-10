from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class ChunkBuilderConfig:
    passages_root: Path = Path("./data/preprocessed/passages")
    output_root: Path = Path("./data/preprocessed/chunks")
    skip_empty_content: bool = True
