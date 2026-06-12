from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List


def _default_ai_service_url() -> str:
    return (os.getenv("AI_SERVICE_URL") or "http://127.0.0.1:8001").rstrip("/")


@dataclass
class ServerConfig:
    ai_service_url: str = field(default_factory=_default_ai_service_url)
    cors_origins: List[str] = field(default_factory=lambda: [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ])
