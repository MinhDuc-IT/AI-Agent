from __future__ import annotations

from typing import Any, Dict, List, Optional

SYSTEM_PROMPT = (
    "Bạn là trợ lý tra cứu pháp luật Việt Nam. "
    "Chỉ trả lời dựa trên các đoạn văn bản pháp luật trong CONTEXT được cung cấp. "
    "Trả lời bằng tiếng Việt, rõ ràng, súc tích. "
    "Khi trích dẫn, nêu số hiệu văn bản và vị trí (Điều/Khoản/Điểm) nếu có trong context. "
    "Nếu CONTEXT không đủ thông tin để trả lời chính xác, hãy nói rõ là không tìm thấy "
    "đủ căn cứ trong tài liệu đã truy xuất — không suy diễn hay bịa thêm."
)


def _format_effectivity(effective_from: Any, effective_to: Any) -> str:
    start = effective_from or "không rõ"
    end = effective_to or "không xác định"
    return f"{start} → {end}"


def format_chunks_context(chunks: List[Dict[str, Any]]) -> str:
    if not chunks:
        return "(Không truy xuất được đoạn văn bản nào.)"

    blocks: List[str] = []
    for idx, chunk in enumerate(chunks, start=1):
        document_number = (chunk.get("document_number") or "").strip() or "không rõ"
        document_title = (chunk.get("document_title") or "").strip()
        path_text = (chunk.get("path_text") or "").strip() or "không rõ"
        content = (chunk.get("content") or "").strip() or "(trống)"
        effectivity = _format_effectivity(
            chunk.get("effective_from"),
            chunk.get("effective_to"),
        )

        header = f"[Nguồn {idx}] Số hiệu: {document_number}"
        if document_title:
            header += f"\nTiêu đề: {document_title}"
        blocks.append(
            "\n".join([
                header,
                f"Vị trí: {path_text}",
                f"Hiệu lực: {effectivity}",
                f"Nội dung: {content}",
            ])
        )
    return "\n\n".join(blocks)


def build_messages(
    query: str,
    chunks: List[Dict[str, Any]],
    *,
    as_of_date: Optional[str] = None,
) -> List[Dict[str, str]]:
    context = format_chunks_context(chunks)
    as_of_line = f"\nNgày tra cứu (as-of): {as_of_date}" if as_of_date else ""
    user_content = (
        f"CÂU HỎI:\n{query}{as_of_line}\n\n"
        f"CONTEXT:\n{context}\n\n"
        "TRẢ LỜI:"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
