from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from src.pipeline.core.llm import OpenRouterLLM
from src.pipeline.prompts.answer import ANSWER_SYSTEM_PROMPT, build_answer_user_prompt


@dataclass
class AnswerResult:
    answer: str
    contexts: List[Dict[str, Any]]
    model: Optional[str] = None


class AnswerAgent:
    def __init__(self, llm: Optional[OpenRouterLLM] = None):
        self.llm = llm or OpenRouterLLM()

    def answer(
        self,
        question: str,
        contexts: Optional[Iterable[Dict[str, Any]]] = None,
        *,
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
    ) -> AnswerResult:
        context_rows = list(contexts or [])
        response = self.llm.complete(
            system_prompt=ANSWER_SYSTEM_PROMPT,
            user_prompt=build_answer_user_prompt(question, context_rows),
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return AnswerResult(
            answer=response.content.strip(),
            contexts=context_rows,
            model=response.model,
        )
