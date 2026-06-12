from __future__ import annotations

from typing import Any, Dict, Iterator, List, Optional

from legal_rag.config import RetrieveConfig
from legal_rag.retriever import ChunkRetriever

from .client import OpenRouterClient
from .config import GeneratorConfig
from .prompt import build_messages


class LegalQAGenerator:
    def __init__(
        self,
        retriever_config: RetrieveConfig,
        generator_config: GeneratorConfig | None = None,
    ):
        self.retriever = ChunkRetriever(retriever_config)
        self.generator_config = generator_config or GeneratorConfig()
        self.llm = OpenRouterClient(self.generator_config)

    def ask(
        self,
        query: str,
        *,
        as_of_date: Optional[str] = None,
        document_number: Optional[str] = None,
        top_k: Optional[int] = None,
    ) -> Dict[str, Any]:
        sources = self.retriever.search(
            query,
            as_of_date=as_of_date,
            document_number=document_number,
            top_k=top_k,
        )
        messages = build_messages(query, sources, as_of_date=as_of_date)
        answer = self.llm.complete(messages)
        return {
            "query": query,
            "answer": answer,
            "sources": sources,
            "as_of": as_of_date,
            "document_number": document_number,
            "model": self.generator_config.model,
        }

    def ask_stream(
        self,
        query: str,
        *,
        as_of_date: Optional[str] = None,
        document_number: Optional[str] = None,
        top_k: Optional[int] = None,
    ) -> Iterator[Dict[str, Any]]:
        sources = self.retriever.search(
            query,
            as_of_date=as_of_date,
            document_number=document_number,
            top_k=top_k,
        )
        yield {
            "type": "sources",
            "query": query,
            "sources": sources,
            "as_of": as_of_date,
            "document_number": document_number,
            "model": self.generator_config.model,
        }

        messages = build_messages(query, sources, as_of_date=as_of_date)
        parts: List[str] = []
        for token in self.llm.stream(messages):
            parts.append(token)
            yield {"type": "token", "content": token}

        yield {
            "type": "done",
            "answer": "".join(parts).strip(),
            "model": self.generator_config.model,
        }
