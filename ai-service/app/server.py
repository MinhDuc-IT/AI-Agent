from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .deps import AppState, ServiceConfig, build_app_state
from .models import ChatRequest, ChatResponse, HealthResponse, source_from_dict
from .sse import encode_sse, encode_sse_error

logger = logging.getLogger(__name__)

_service_config: Optional[ServiceConfig] = None
_app_state: Optional[AppState] = None
_cors_applied = False


def configure_service(config: ServiceConfig) -> None:
    global _service_config
    _service_config = config
    setup_cors(config.cors_origins)


def get_app_state() -> AppState:
    if _app_state is None:
        raise RuntimeError("AI service not initialized.")
    return _app_state


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
    global _app_state
    config = _service_config or ServiceConfig()
    logger.info("Loading embedder and Qdrant client (may take ~30-60s)...")
    _app_state = build_app_state(config)
    logger.info("AI service ready. Qdrant: %s | Model: %s", _app_state.qdrant_target, _app_state.model)
    yield
    _app_state = None


app = FastAPI(
    title="Legal QA AI Service",
    description="RAG retrieval + LLM generation with SSE streaming",
    lifespan=lifespan,
)


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    state = get_app_state()
    return HealthResponse(
        status="ok",
        model=state.model,
        qdrant_target=state.qdrant_target,
        ready=True,
    )


@app.post("/api/chat", response_model=ChatResponse)
def chat(body: ChatRequest) -> ChatResponse:
    message = body.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Câu hỏi không được để trống.")

    state = get_app_state()
    try:
        result = state.generator.ask(
            message,
            as_of_date=body.as_of,
            document_number=body.document_number,
            top_k=body.top_k,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("chat failed")
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý: {exc}") from exc

    return ChatResponse(
        query=result["query"],
        answer=result["answer"],
        sources=[source_from_dict(row) for row in result.get("sources", [])],
        model=result.get("model") or state.model,
        as_of=result.get("as_of"),
        document_number=result.get("document_number"),
    )


@app.post("/api/chat/stream")
def chat_stream(body: ChatRequest) -> StreamingResponse:
    message = body.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Câu hỏi không được để trống.")

    state = get_app_state()

    def event_stream():
        try:
            for event in state.generator.ask_stream(
                message,
                as_of_date=body.as_of,
                document_number=body.document_number,
                top_k=body.top_k,
            ):
                yield encode_sse(event)
        except FileNotFoundError as exc:
            yield encode_sse_error(str(exc))
        except ValueError as exc:
            yield encode_sse_error(str(exc))
        except Exception as exc:
            logger.exception("chat stream failed")
            yield encode_sse_error(f"Lỗi xử lý: {exc}")

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
