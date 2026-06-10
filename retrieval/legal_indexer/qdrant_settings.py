from __future__ import annotations

from pathlib import Path
from typing import Optional

from .config import IndexerConfig, SearcherConfig
from .env import load_qdrant_env


def apply_qdrant_settings(
    config: IndexerConfig | SearcherConfig,
    *,
    qdrant_url: Optional[str] = None,
    qdrant_api_key: Optional[str] = None,
    use_local: bool = False,
) -> IndexerConfig | SearcherConfig:
    env = load_qdrant_env(use_local=use_local)

    if qdrant_url:
        config.qdrant_url = qdrant_url
    elif env.url and not use_local:
        config.qdrant_url = env.url

    if qdrant_api_key:
        config.qdrant_api_key = qdrant_api_key
    elif env.api_key and not use_local:
        config.qdrant_api_key = env.api_key

    return config


def qdrant_target_label(config: IndexerConfig | SearcherConfig) -> str:
    if config.qdrant_url:
        return f"cloud:{config.qdrant_url}"
    return f"local:{Path(config.qdrant_path)}"
