from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import uvicorn

from app.deps import ServiceConfig
from app.server import app, configure_service


def _configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


def main() -> None:
    _configure_stdout()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    ap = argparse.ArgumentParser(description="Legal QA AI service (RAG + SSE)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8001)
    ap.add_argument("--qdrant-path", default=None)
    ap.add_argument("--qdrant-url", default=None)
    ap.add_argument("--qdrant-api-key", default=None)
    ap.add_argument("--local-qdrant", action="store_true")
    ap.add_argument("--collection", default="legal_chunks")
    ap.add_argument("--dense-model", default="bkai-foundation-models/vietnamese-bi-encoder")
    ap.add_argument("--sparse-model", default="Qdrant/bm25")
    ap.add_argument("--device", default=None)
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--model", default="openai/gpt-4o-mini")
    ap.add_argument("--max-tokens", type=int, default=1024)
    ap.add_argument("--temperature", type=float, default=0.0)
    args = ap.parse_args()

    qdrant_path = Path(args.qdrant_path) if args.qdrant_path else None
    configure_service(ServiceConfig(
        qdrant_path=qdrant_path or ServiceConfig().qdrant_path,
        qdrant_url=args.qdrant_url,
        qdrant_api_key=args.qdrant_api_key,
        use_local_qdrant=args.local_qdrant,
        collection=args.collection,
        dense_model=args.dense_model,
        sparse_model=args.sparse_model,
        device=args.device,
        top_k=args.top,
        llm_model=args.model,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
    ))

    print(f"AI service: http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
