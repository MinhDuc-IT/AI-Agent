from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from qdrant_client import models

PAYLOAD_INDEX_FIELDS = (
    ("document_number", models.PayloadSchemaType.KEYWORD),
    ("effective_from_int", models.PayloadSchemaType.INTEGER),
    ("effective_to_int", models.PayloadSchemaType.INTEGER),
)


def date_to_int(value: Optional[str]) -> Optional[int]:
    if value in {None, "", "null"}:
        return None
    match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", str(value).strip())
    if not match:
        return None
    return int(f"{match.group(1)}{match.group(2)}{match.group(3)}")


def build_retrieval_filter(
    as_of_date: Optional[str] = None,
    document_number: Optional[str] = None,
) -> Optional[models.Filter]:
    must: List[models.Condition] = []

    if document_number:
        must.append(
            models.FieldCondition(
                key="document_number",
                match=models.MatchValue(value=document_number),
            )
        )

    as_of_int = date_to_int(as_of_date)
    if as_of_int is not None:
        must.append(
            models.Filter(
                should=[
                    models.FieldCondition(key="effective_from_int", is_null=True),
                    models.FieldCondition(
                        key="effective_from_int",
                        range=models.Range(lte=as_of_int),
                    ),
                ]
            )
        )
        must.append(
            models.Filter(
                should=[
                    models.FieldCondition(key="effective_to_int", is_null=True),
                    models.FieldCondition(
                        key="effective_to_int",
                        range=models.Range(gt=as_of_int),
                    ),
                ]
            )
        )

    if not must:
        return None
    return models.Filter(must=must)


build_query_filter = build_retrieval_filter


def chunk_payload(chunk: Dict[str, Any], chunk_text: str) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "chunk_id": chunk.get("chunk_id"),
        "source_unit_ids": chunk.get("source_unit_ids") or [],
        "document_number": chunk.get("document_number"),
        "document_title": chunk.get("document_title"),
        "document_type": chunk.get("document_type"),
        "path_text": chunk.get("path_text"),
        "content": chunk.get("content"),
        "source_file": chunk.get("source_file"),
        "source_url": chunk.get("source_url"),
        "chunk_text": chunk_text,
    }
    effective_from = chunk.get("effective_from")
    effective_to = chunk.get("effective_to")
    if effective_from not in {None, "", "null"}:
        payload["effective_from"] = effective_from
        from_int = date_to_int(str(effective_from))
        if from_int is not None:
            payload["effective_from_int"] = from_int
    if effective_to not in {None, "", "null"}:
        payload["effective_to"] = effective_to
        to_int = date_to_int(str(effective_to))
        if to_int is not None:
            payload["effective_to_int"] = to_int
    return payload
