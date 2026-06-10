from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GeneratorConfig:
    model: str = "openai/gpt-4o-mini"
    base_url: str = "https://openrouter.ai/api/v1"
    max_tokens: int = 1024
    temperature: float = 0.0
