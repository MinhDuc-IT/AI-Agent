from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    as_of: Optional[str] = Field(None, description="Ngày tra cứu hiệu lực (YYYY-MM-DD)")
    document_number: Optional[str] = Field(None, description="Lọc theo số hiệu văn bản")
    top_k: int = Field(5, ge=1, le=20)


class SourceItem(BaseModel):
    score: Optional[float] = None
    chunk_id: Optional[str] = None
    document_number: Optional[str] = None
    document_title: Optional[str] = None
    path_text: Optional[str] = None
    content: Optional[str] = None
    effective_from: Optional[str] = None
    effective_to: Optional[str] = None


class ChatResponse(BaseModel):
    query: str
    answer: str
    sources: List[SourceItem]
    model: str
    as_of: Optional[str] = None
    document_number: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    model: str
    qdrant_target: str
    ready: bool


def source_from_dict(row: Dict[str, Any]) -> SourceItem:
    return SourceItem(
        score=row.get("score"),
        chunk_id=row.get("chunk_id"),
        document_number=row.get("document_number"),
        document_title=row.get("document_title"),
        path_text=row.get("path_text"),
        content=row.get("content"),
        effective_from=row.get("effective_from"),
        effective_to=row.get("effective_to"),
    )
