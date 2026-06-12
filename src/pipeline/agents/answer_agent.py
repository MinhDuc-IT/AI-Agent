from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from src.pipeline.core.llm import LLMResponse, OpenRouterLLM
from src.pipeline.prompts.answer import ANSWER_SYSTEM_PROMPT, build_answer_user_prompt


@dataclass
class AnswerResult:
    answer: str
    citations: List[Dict[str, Any]]
    model: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None


class AnswerAgent:
    def __init__(self, llm: Optional[OpenRouterLLM] = None, *, model: Optional[str] = None):
        self.llm = llm or OpenRouterLLM()
        self.model = model

    def answer(
        self,
        question: str,
        *,
        contexts: Optional[Iterable[Dict[str, Any]]] = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
    ) -> AnswerResult:
        context_rows = list(contexts or [])
        user_prompt = build_answer_user_prompt(question, context_rows)
        response: LLMResponse = self.llm.complete(
            system_prompt=ANSWER_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            model=self.model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return AnswerResult(
            answer=response.content.strip(),
            citations=self._citations(context_rows),
            model=response.model,
            raw_response=response.raw,
        )

    @staticmethod
    def _citations(contexts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        citations: List[Dict[str, Any]] = []
        for item in contexts:
            citations.append({
                "chunk_id": item.get("chunk_id"),
                "document_number": item.get("document_number"),
                "document_title": item.get("document_title"),
                "path_text": item.get("path_text"),
                "effective_from": item.get("effective_from"),
                "effective_to": item.get("effective_to"),
                "source_file": item.get("source_file"),
                "source_url": item.get("source_url"),
            })
        return citations
