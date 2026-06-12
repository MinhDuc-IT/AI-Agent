from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from typing import List, Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .deps import ServerConfig
from .models import ChatRequest, ChatResponse, HealthResponse

logger = logging.getLogger(__name__)

_server_config: Optional[ServerConfig] = None
_http_client: Optional[httpx.AsyncClient] = None
_cors_applied = False


def configure_server(config: ServerConfig) -> None:
    global _server_config
    _server_config = config
    setup_cors(config.cors_origins)


def get_config() -> ServerConfig:
    return _server_config or ServerConfig()


def get_http_client() -> httpx.AsyncClient:
    if _http_client is None:
        raise RuntimeError("HTTP client not initialized.")
    return _http_client


def setup_cors(origins: List[str]) -> None:
    global _cors_applied
    if _cors_applied:
        return
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    _cors_applied = True


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _http_client
    config = get_config()
    _http_client = httpx.AsyncClient(
        base_url=config.ai_service_url,
        timeout=httpx.Timeout(300.0, connect=10.0),
    )
    logger.info("Backend ready. AI service: %s", config.ai_service_url)
    yield
    await _http_client.aclose()
    _http_client = None


app = FastAPI(
    title="Legal QA API",
    description="BFF proxy tới AI service (RAG + SSE streaming)",
    lifespan=lifespan,
)


@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    client = get_http_client()
    try:
        response = await client.get("/api/health")
        response.raise_for_status()
        data = response.json()
        return HealthResponse(
            status=data.get("status", "ok"),
            model=data.get("model", ""),
            qdrant_target=data.get("qdrant_target", ""),
            ready=bool(data.get("ready")),
        )
    except httpx.HTTPError as exc:
        logger.warning("AI service health check failed: %s", exc)
        return HealthResponse(
            status="degraded",
            model="",
            qdrant_target=get_config().ai_service_url,
            ready=False,
        )


@app.post("/api/chat", response_model=ChatResponse)
async def chat(body: ChatRequest) -> ChatResponse:
    client = get_http_client()
    try:
        response = await client.post("/api/chat", json=body.model_dump())
        if response.status_code >= 400:
            detail = response.json().get("detail", response.text)
            raise HTTPException(status_code=response.status_code, detail=detail)
        return ChatResponse(**response.json())
    except httpx.HTTPError as exc:
        logger.exception("proxy chat failed")
        raise HTTPException(
            status_code=503,
            detail=f"Không kết nối được AI service tại {get_config().ai_service_url}",
        ) from exc


@app.post("/api/chat/stream")
async def chat_stream(body: ChatRequest) -> StreamingResponse:
    client = get_http_client()
    request = client.build_request(
        "POST",
        "/api/chat/stream",
        json=body.model_dump(),
        headers={"Accept": "text/event-stream"},
    )

    try:
        response = await client.send(request, stream=True)
    except httpx.HTTPError as exc:
        logger.exception("proxy stream connect failed")
        raise HTTPException(
            status_code=503,
            detail=f"Không kết nối được AI service tại {get_config().ai_service_url}",
        ) from exc

    if response.status_code >= 400:
        text = await response.aread()
        await response.aclose()
        try:
            detail = json.loads(text).get("detail", text.decode(errors="replace"))
        except Exception:
            detail = text.decode(errors="replace")
        raise HTTPException(status_code=response.status_code, detail=detail)

    async def proxy_stream():
        try:
            async for chunk in response.aiter_bytes():
                yield chunk
        finally:
            await response.aclose()

    return StreamingResponse(
        proxy_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
