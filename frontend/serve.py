from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser(description="Serve Legal QA frontend (static files)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=5173)
    args = ap.parse_args()

    root = Path(__file__).resolve().parent
    handler = partial(SimpleHTTPRequestHandler, directory=str(root))
    server = ThreadingHTTPServer((args.host, args.port), handler)

    print(f"Frontend: http://{args.host}:{args.port}")
    print("Ensure backend is running: cd backend && python main.py")
    print("Edit frontend/config.js to change API URL if needed.")
    server.serve_forever()


if __name__ == "__main__":
    main()
