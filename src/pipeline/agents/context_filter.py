from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional


@dataclass(frozen=True)
class AnswerContextFilter:
    document_number: Optional[str] = None
    as_of_date: Optional[str] = None
    top_k: Optional[int] = None
    min_score: Optional[float] = None
    mode: Optional[str] = None


def date_to_int(value: Optional[str]) -> Optional[int]:
    if value in {None, "", "null"}:
        return None
    match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", str(value).strip())
    if not match:
        return None
    return int(f"{match.group(1)}{match.group(2)}{match.group(3)}")


def is_effective_as_of(context: Dict[str, Any], as_of_date: Optional[str]) -> bool:
    as_of_int = date_to_int(as_of_date)
    if as_of_int is None:
        return True

    effective_from = date_to_int(context.get("effective_from"))
    if effective_from is not None and effective_from > as_of_int:
        return False

    effective_to = date_to_int(context.get("effective_to"))
    if effective_to is not None and effective_to <= as_of_int:
        return False

    return True


def filter_contexts(
    contexts: Iterable[Dict[str, Any]],
    context_filter: Optional[AnswerContextFilter] = None,
    *,
    document_number: Optional[str] = None,
    as_of_date: Optional[str] = None,
    top_k: Optional[int] = None,
    min_score: Optional[float] = None,
    mode: Optional[str] = None,
) -> List[Dict[str, Any]]:
    active_filter = context_filter or AnswerContextFilter(
        document_number=document_number,
        as_of_date=as_of_date,
        top_k=top_k,
        min_score=min_score,
        mode=mode,
    )

    rows: List[Dict[str, Any]] = []
    expected_document_number = _clean(active_filter.document_number)
    expected_mode = _clean(active_filter.mode)

    for item in contexts:
        if not isinstance(item, dict):
            raise TypeError("Answer contexts must be dictionaries shaped like retrieve results.")

        if expected_document_number and _clean(item.get("document_number")) != expected_document_number:
            continue
        if expected_mode and _clean(item.get("mode")) != expected_mode:
            continue
        if active_filter.min_score is not None and not _score_at_least(item, active_filter.min_score):
            continue
        if not is_effective_as_of(item, active_filter.as_of_date):
            continue

        rows.append(item)

    if active_filter.top_k is not None:
        rows = rows[:max(0, active_filter.top_k)]
    return rows


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _score_at_least(context: Dict[str, Any], min_score: float) -> bool:
    try:
        score = float(context.get("score"))
    except (TypeError, ValueError):
        return False
    return score >= min_score
