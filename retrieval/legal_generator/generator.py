from __future__ import annotations

from typing import Any, Dict, List, Optional

from legal_indexer.config import SearcherConfig
from legal_indexer.searcher import ChunkSearcher

from .client import OpenRouterClient
from .config import GeneratorConfig
from .prompt import build_messages


class LegalQAGenerator:
    def __init__(
        self,
        searcher_config: SearcherConfig,
        generator_config: GeneratorConfig | None = None,
    ):
        self.searcher = ChunkSearcher(searcher_config)
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
        sources = self.searcher.search(
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
