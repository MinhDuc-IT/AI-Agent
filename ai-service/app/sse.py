from __future__ import annotations

import json
from typing import Any, Dict


def encode_sse(event: Dict[str, Any]) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def encode_sse_error(message: str) -> str:
    return encode_sse({"type": "error", "message": message})
