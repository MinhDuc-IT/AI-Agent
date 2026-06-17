from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from .context_filter import AnswerContextFilter, filter_contexts
from ..core.llm import OpenRouterLLM
from ..prompts.answer import ANSWER_SYSTEM_PROMPT, build_answer_user_prompt


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
        context_filter: Optional[AnswerContextFilter] = None,
        document_number: Optional[str] = None,
        as_of_date: Optional[str] = None,
        top_k: Optional[int] = None,
        min_score: Optional[float] = None,
        mode: Optional[str] = None,
    ) -> AnswerResult:
        context_rows = filter_contexts(
            contexts or [],
            context_filter,
            document_number=document_number,
            as_of_date=as_of_date,
            top_k=top_k,
            min_score=min_score,
            mode=mode,
        )
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
