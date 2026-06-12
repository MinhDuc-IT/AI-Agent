from __future__ import annotations

from typing import Dict, Iterator, List

from openai import OpenAI

from .config import GeneratorConfig
from .env import get_openrouter_api_key


class OpenRouterClient:
    def __init__(self, config: GeneratorConfig):
        self.config = config
        self._client = OpenAI(
            base_url=config.base_url,
            api_key=get_openrouter_api_key(),
        )

    def complete(self, messages: List[Dict[str, str]]) -> str:
        response = self._client.chat.completions.create(
            model=self.config.model,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            messages=messages,
        )
        content = response.choices[0].message.content
        return (content or "").strip()

    def stream(self, messages: List[Dict[str, str]]) -> Iterator[str]:
        response = self._client.chat.completions.create(
            model=self.config.model,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            messages=messages,
            stream=True,
        )
        for chunk in response:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
