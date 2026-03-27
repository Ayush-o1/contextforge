"""FastAPI application entry point for ContextForge."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from redis.asyncio import Redis

from app import telemetry as tel
from app.cache import SemanticCache
from app.compressor import compress_context
from app.config import Settings, get_settings
from app.embedder import Embedder
from app.models import ChatCompletionRequest, HealthResponse
from app.proxy import ProxyClient, UpstreamError
from app.router import ModelRouter
from app.vector_store import VectorStore

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifecycle — initialize and teardown resources."""
    settings: Settings = get_settings()

    # --- Proxy client ---
    proxy_client = ProxyClient(settings)
    application.state.proxy_client = proxy_client
    application.state.settings = settings

    # --- Embedding model ---
    embedder = Embedder()
    application.state.embedder = embedder

    # --- Vector store (FAISS) ---
    vector_store = VectorStore(
        dimension=embedder.dimension,
        index_path=settings.faiss_index_path,
    )
    application.state.vector_store = vector_store

    # --- Redis ---
    redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    application.state.redis = redis_client

    # --- Semantic cache ---
    cache = SemanticCache(
        embedder=embedder,
        vector_store=vector_store,
        redis=redis_client,
        settings=settings,
    )
    application.state.cache = cache

    # --- Model router ---
    router = ModelRouter(
        config_path="config/routing_rules.yaml",
        preferred_provider=settings.preferred_provider,
    )
    application.state.router = router

    # --- Telemetry DB ---
    tel.init_db()

    logger.info("contextforge.started", log_level=settings.log_level)
    yield

    # --- Shutdown ---
    await cache.close()
    await proxy_client.close()
    logger.info("contextforge.shutdown")


app = FastAPI(
    title="ContextForge",
    description="Proxy middleware for LLM-powered apps",
    version="0.4.0",
    lifespan=lifespan,
)


# ───────────────────────── Health Check ──────────────────────────────────


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Simple health check endpoint."""
    return HealthResponse()


# ─────────────────── Chat Completions Endpoint ───────────────────────────


@app.post("/v1/chat/completions", response_model=None)
async def chat_completions(request: Request, body: ChatCompletionRequest):
    """OpenAI-compatible chat completions endpoint.

    Pipeline:
      1. Route model (classify complexity → select tier)
      2. Compress context if conversation is long
      3. Check semantic cache for a similar prompt
      4. On cache hit → return cached response immediately
      5. On cache miss → forward to upstream, cache the result
    Streaming requests bypass cache and compression.
    """
    proxy_client: ProxyClient = request.app.state.proxy_client
    cache: SemanticCache = request.app.state.cache
    router: ModelRouter = request.app.state.router

    try:
        messages_dicts = [m.model_dump(exclude_none=True) for m in body.messages]

        # --- Model routing ---
        override_model = request.headers.get("x-contextforge-model-override")
        routing = router.route(body.model, messages_dicts, override_model=override_model)

        # Streaming bypasses cache and compression
        if body.stream:
            return StreamingResponse(
                proxy_client.forward_stream(body, model_override=routing.model_selected),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                    "X-Model-Tier": routing.tier.value,
                    "X-Model-Selected": routing.model_selected,
                },
            )

        # --- Context compression ---
        no_compress = request.headers.get("x-contextforge-no-compress") == "true"
        compression_ratio = 1.0
        compressed_messages = messages_dicts

        if not no_compress:
            compressed_messages, compression_ratio = await compress_context(
                messages_dicts,
                body.model,
                proxy_client,
                request.app.state.settings,
            )
            # Update body.messages so forward() sends compressed messages upstream
            body.messages = [
                body.messages[0].__class__(**m) for m in compressed_messages
            ]

        # --- Semantic cache lookup ---
        cache_result = await cache.lookup(body.model, compressed_messages)

        if cache_result.hit:
            # --- Telemetry: cache hit ---
            request.state.model_requested = body.model
            request.state.model_used = routing.model_selected
            request.state.cache_hit = True
            request.state.similarity_score = cache_result.similarity_score
            request.state.prompt_tokens = 0
            request.state.completion_tokens = 0
            request.state.compressed = not no_compress
            request.state.compression_ratio = compression_ratio

            return JSONResponse(
                content=cache_result.response,
                headers={
                    "X-Cache": "HIT",
                    "X-Similarity": str(cache_result.similarity_score),
                    "X-Model-Tier": routing.tier.value,
                    "X-Model-Selected": routing.model_selected,
                    "X-Compressed": str(not no_compress),
                    "X-Compression-Ratio": str(compression_ratio),
                },
            )

        # --- Cache miss: forward upstream with routed model ---
        response_data = await proxy_client.forward(body, model_override=routing.model_selected)

        # Store in cache
        await cache.store(body.model, compressed_messages, response_data)

        # --- Telemetry: cache miss ---
        usage = response_data.get("usage") or {}
        request.state.model_requested = body.model
        request.state.model_used = routing.model_selected
        request.state.cache_hit = False
        request.state.similarity_score = None
        request.state.prompt_tokens = usage.get("prompt_tokens", 0)
        request.state.completion_tokens = usage.get("completion_tokens", 0)
        request.state.compressed = not no_compress
        request.state.compression_ratio = compression_ratio

        return JSONResponse(
            content=response_data,
            headers={
                "X-Cache": "MISS",
                "X-Model-Tier": routing.tier.value,
                "X-Model-Selected": routing.model_selected,
                "X-Compressed": str(not no_compress),
                "X-Compression-Ratio": str(compression_ratio),
            },
        )

    except UpstreamError as exc:
        logger.warning("upstream.error", status_code=exc.status_code, detail=exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "message": exc.detail,
                    "type": "upstream_error",
                    "code": str(exc.status_code),
                }
            },
        )


# ─────────────────── Telemetry Endpoints ─────────────────────────────────


@app.get("/v1/telemetry")
async def get_telemetry(limit: int = 50, offset: int = 0):
    return {"records": tel.get_records(limit, offset), "limit": limit, "offset": offset}


@app.get("/v1/telemetry/summary")
async def get_telemetry_summary():
    return tel.get_summary()
