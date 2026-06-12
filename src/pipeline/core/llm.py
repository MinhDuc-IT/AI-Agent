from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

Message = Dict[str, str]


def load_dotenv(path: Optional[Path] = None) -> Optional[Path]:
    env_path = path or find_project_root() / ".env"
    if not env_path.exists():
        return None

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
    return env_path


def find_project_root(start: Optional[Path] = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".env").exists():
            return candidate
        if (candidate / "src" / "pipeline").exists() and (candidate / "data").exists():
            return candidate
    return current


@dataclass
class LLMConfig:
    api_key: str
    base_url: str = "https://openrouter.ai/api/v1"
    model: str = "openai/gpt-4o-mini"
    timeout_seconds: int = 120
    temperature: float = 0.2
    max_tokens: Optional[int] = None
    app_url: Optional[str] = None
    app_name: Optional[str] = None

    @classmethod
    def from_env(cls, env_path: Optional[Path] = None) -> "LLMConfig":
        load_dotenv(env_path)
        api_key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
        if not api_key:
            raise RuntimeError("Missing OPENROUTER_API_KEY in environment or .env")
        return cls(
            api_key=api_key,
            base_url=(os.getenv("OPENROUTER_BASE_URL") or cls.base_url).strip().rstrip("/"),
            model=(os.getenv("OPENROUTER_MODEL") or cls.model).strip(),
            app_url=(os.getenv("OPENROUTER_APP_URL") or "").strip() or None,
            app_name=(os.getenv("OPENROUTER_APP_NAME") or "").strip() or None,
        )


@dataclass
class LLMResponse:
    content: str
    model: Optional[str]
    raw: Dict[str, Any]


class OpenRouterLLM:
    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig.from_env()

    def chat(
        self,
        messages: Sequence[Message],
        *,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        payload: Dict[str, Any] = {
            "model": model or self.config.model,
            "messages": list(messages),
            "temperature": self.config.temperature if temperature is None else temperature,
        }
        token_limit = self.config.max_tokens if max_tokens is None else max_tokens
        if token_limit is not None:
            payload["max_tokens"] = token_limit

        data = self._post_json("/chat/completions", payload)
        choices = data.get("choices") or []
        content = ""
        if choices:
            message = choices[0].get("message") or {}
            content = message.get("content") or ""
        return LLMResponse(content=content, model=data.get("model"), raw=data)

    def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        return self.chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def _post_json(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = self.config.base_url.rstrip("/") + "/" + path.lstrip("/")
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        if self.config.app_url:
            headers["HTTP-Referer"] = self.config.app_url
        if self.config.app_name:
            headers["X-Title"] = self.config.app_name

        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenRouter API error {exc.code}: {error_body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"OpenRouter request failed: {exc}") from exc
