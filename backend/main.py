from __future__ import annotations

import argparse
import logging
import os
import sys

import uvicorn

from app.deps import ServerConfig
from app.server import app, configure_server


def _configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


def _load_dotenv() -> None:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(os.path.dirname(root), ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def main() -> None:
    _configure_stdout()
    _load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    ap = argparse.ArgumentParser(description="Legal QA API backend (BFF proxy)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument(
        "--ai-service-url",
        default=os.getenv("AI_SERVICE_URL", "http://127.0.0.1:8001"),
        help="URL of ai-service",
    )
    ap.add_argument(
        "--cors-origin",
        action="append",
        dest="cors_origins",
        help="Allowed CORS origin (repeatable)",
    )
    args = ap.parse_args()

    cors_origins = args.cors_origins or [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ]

    configure_server(ServerConfig(
        ai_service_url=args.ai_service_url.rstrip("/"),
        cors_origins=cors_origins,
    ))

    print(f"API (BFF): http://{args.host}:{args.port}")
    print(f"AI service: {args.ai_service_url}")
    print("Start AI service: cd ai-service && python main.py")
    print("Start frontend: cd frontend && python serve.py")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
