from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

ANSWER_SYSTEM_PROMPT = """Bạn là trợ lý hỏi đáp pháp luật Việt Nam.
Chỉ trả lời dựa trên ngữ cảnh được cung cấp khi có ngữ cảnh.
Nếu ngữ cảnh không đủ để kết luận, nói rõ là chưa đủ dữ liệu.
Ưu tiên câu trả lời ngắn, trực tiếp, nêu căn cứ theo văn bản và đường dẫn pháp lý.
Không tự bịa số điều, hiệu lực, mức phạt hoặc ngoại lệ."""


def build_answer_user_prompt(
    question: str,
    contexts: Optional[Iterable[Dict[str, Any]]] = None,
) -> str:
    context_text = format_contexts(contexts or [])
    if not context_text:
        return f"Câu hỏi:\n{question.strip()}"
    return "\n\n".join([
        "Ngữ cảnh truy xuất:",
        context_text,
        "Câu hỏi:",
        question.strip(),
        "Yêu cầu trả lời:",
        "- Trả lời bằng tiếng Việt.",
        "- Dẫn nguồn bằng chunk_id hoặc đường dẫn pháp lý khi dùng thông tin từ ngữ cảnh.",
        "- Nếu các chunk mâu thuẫn hoặc thiếu dữ liệu, nêu rõ giới hạn đó.",
    ])


def format_contexts(contexts: Iterable[Dict[str, Any]]) -> str:
    blocks: List[str] = []
    for idx, item in enumerate(contexts, start=1):
        chunk_id = item.get("chunk_id") or f"context_{idx}"
        document_number = item.get("document_number") or ""
        document_title = item.get("document_title") or ""
        path_text = item.get("path_text") or ""
        effective_from = item.get("effective_from") or ""
        effective_to = item.get("effective_to") or ""
        content = (item.get("content") or "").strip()
        parts = [
            f"[{idx}] chunk_id: {chunk_id}",
            f"document_number: {document_number}",
        ]
        if document_title:
            parts.append(f"document_title: {document_title}")
        if path_text:
            parts.append(f"path_text: {path_text}")
        if effective_from or effective_to:
            parts.append(f"effective: {effective_from or 'không rõ'} -> {effective_to or 'không rõ'}")
        parts.append("content:")
        parts.append(content)
        blocks.append("\n".join(parts))
    return "\n\n".join(blocks)
