from __future__ import annotations

import os

from legal_indexer.env import load_dotenv_file

OPENROUTER_API_KEY_ENV = "OPENROUTER_API_KEY"


def get_openrouter_api_key(*, required: bool = True) -> str | None:
    load_dotenv_file()
    api_key = (os.getenv(OPENROUTER_API_KEY_ENV) or "").strip() or None
    if required and not api_key:
        raise ValueError(
            f"Set {OPENROUTER_API_KEY_ENV} in your environment or .env before calling ask()."
        )
    return api_key
