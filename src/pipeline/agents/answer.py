from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline.agents.answer_agent import AnswerAgent


def _configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


def _load_contexts(path: str | None) -> List[Dict[str, Any]]:
    if not path:
        return []
    context_path = Path(path)
    if not context_path.exists():
        raise FileNotFoundError(f"Context file not found: {context_path}")
    if context_path.suffix.lower() == ".jsonl":
        rows = []
        with context_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        return rows
    data = json.loads(context_path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("contexts", "sources", "results"):
            if isinstance(data.get(key), list):
                return data[key]
    raise ValueError("Context file must be a JSON list, JSONL file, or object with contexts/sources/results.")


def main() -> None:
    _configure_stdout()
    parser = argparse.ArgumentParser(description="Generate a simple answer from optional retrieved contexts.")
    parser.add_argument("question")
    parser.add_argument("--contexts", default=None, help="JSON/JSONL file containing retrieved context rows.")
    parser.add_argument("--document-number", default=None, help="Filter contexts by retrieved document_number.")
    parser.add_argument("--as-of", dest="as_of", default=None, help="Filter contexts by effective date (YYYY-MM-DD).")
    parser.add_argument("--top", type=int, default=None, help="Use only the first N contexts after filtering.")
    parser.add_argument("--min-score", type=float, default=None, help="Keep contexts with score >= this value.")
    parser.add_argument("--mode", choices=["dense", "sparse", "hybrid"], default=None, help="Filter contexts by retrieval mode.")
    parser.add_argument("--model", default=None)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--max-tokens", type=int, default=None)
    args = parser.parse_args()

    result = AnswerAgent().answer(
        args.question,
        _load_contexts(args.contexts),
        model=args.model,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        document_number=args.document_number,
        as_of_date=args.as_of,
        top_k=args.top,
        min_score=args.min_score,
        mode=args.mode,
    )
    print(result.answer)


if __name__ == "__main__":
    main()
