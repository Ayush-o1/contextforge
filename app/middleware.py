# Phase 1 implementation
import time
import uuid
from datetime import datetime, timezone

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app import telemetry
from app.costs import estimate_cost  # see below


class TelemetryMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Only instrument LLM proxy requests
        if not request.url.path.startswith("/v1/chat"):
            return await call_next(request)

        request_id = str(uuid.uuid4())
        start = time.monotonic()

        response = await call_next(request)

        latency_ms = (time.monotonic() - start) * 1000

        # Pull metadata set by route handler via request.state
        state = request.state
        telemetry.write_record({
            "request_id": request_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model_requested": getattr(state, "model_requested", None),
            "model_used": getattr(state, "model_used", None),
            "cache_hit": getattr(state, "cache_hit", False),
            "similarity_score": getattr(state, "similarity_score", None),
            "prompt_tokens": getattr(state, "prompt_tokens", 0),
            "completion_tokens": getattr(state, "completion_tokens", 0),
            "estimated_cost_usd": estimate_cost(
                getattr(state, "model_used", ""),
                getattr(state, "prompt_tokens", 0),
                getattr(state, "completion_tokens", 0),
            ),
            "latency_ms": round(latency_ms, 2),
            "compressed": getattr(state, "compressed", False),
            "compression_ratio": getattr(state, "compression_ratio", 1.0),
        })
        return response
