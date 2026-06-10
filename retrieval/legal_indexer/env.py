from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class QdrantEnvConfig:
    url: Optional[str] = None
    api_key: Optional[str] = None
    source: str = "local"


def find_project_root(start: Optional[Path] = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".env").exists():
            return candidate
        if (candidate / "data" / "preprocessed").exists() and (candidate / "retrieval").exists():
            return candidate
    return current


def load_dotenv_file(env_path: Optional[Path] = None) -> Optional[Path]:
    path = env_path or (find_project_root() / ".env")
    if not path.exists():
        return None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
    return path


def load_qdrant_env(use_local: bool = False) -> QdrantEnvConfig:
    if not use_local:
        load_dotenv_file()

    url = (os.getenv("QDRANT_URL") or "").strip() or None
    api_key = (os.getenv("QDRANT_API_KEY") or "").strip() or None

    if use_local or not url:
        return QdrantEnvConfig(source="local")

    return QdrantEnvConfig(url=url, api_key=api_key, source="cloud")
