"""Admin API router — cost reporting and request log access.

Endpoints
---------
GET /admin/usage
    Aggregated spend, tokens, and cache-hit-rate summary.
    Optional filters: model, start_date, end_date, user_id.

GET /admin/logs
    Paginated raw request_log rows.
    Optional filters: model, status, start_date, end_date, user_id.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app import telemetry as tel

router = APIRouter(prefix="/admin", tags=["admin"])


# ─── Usage Summary ───────────────────────────────────────────────────────


@router.get("/usage")
async def get_usage(
    model: str | None = Query(default=None, description="Filter by exact model string, e.g. 'openai/gpt-4o'"),
    start_date: str | None = Query(default=None, description="ISO 8601 start datetime, e.g. '2025-01-01T00:00:00'"),
    end_date: str | None = Query(default=None, description="ISO 8601 end datetime, e.g. '2025-12-31T23:59:59'"),
    user_id: str | None = Query(default=None, description="Filter by user_id propagated from the original request"),
) -> dict[str, Any]:
    """Return aggregated usage and cost summary from the request_log table.

    Response fields
    ---------------
    total_requests          : int    — total upstream (non-cached) calls
    total_prompt_tokens     : int
    total_completion_tokens : int
    total_tokens            : int
    total_spend_usd         : float  — sum of litellm.completion_cost() values
    avg_latency_ms          : float
    cache_hit_rate          : float  — from the broader telemetry table
    by_model                : list   — per-model breakdown sorted by spend desc
    filters_applied         : dict   — echo the active filter values
    """
    summary = tel.get_usage_summary(
        model=model,
        start_date=start_date,
        end_date=end_date,
        user_id=user_id,
    )
    summary["filters_applied"] = {
        "model": model,
        "start_date": start_date,
        "end_date": end_date,
        "user_id": user_id,
    }
    return summary


# ─── Raw Logs ────────────────────────────────────────────────────────────


@router.get("/logs")
async def get_logs(
    limit: int = Query(default=50, ge=1, le=500, description="Max rows to return"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    model: str | None = Query(default=None),
    status: str | None = Query(default=None, description="'success', 'cached', or 'error'"),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
) -> dict[str, Any]:
    """Return paginated rows from the request_log table with optional filters."""
    rows = tel.get_request_log(
        limit=limit,
        offset=offset,
        model=model,
        status=status,
        start_date=start_date,
        end_date=end_date,
        user_id=user_id,
    )
    return {
        "records": rows,
        "count": len(rows),
        "limit": limit,
        "offset": offset,
    }


# ─── Total Savings ────────────────────────────────────────────────────────


@router.get("/savings")
async def get_savings() -> dict[str, Any]:
    """Return total cost savings broken down by cache hits and routing efficiency.

    Two savings streams
    -------------------
    cache_savings_usd   : cost avoided by serving requests from cache (free)
    routing_savings_usd : cost avoided by using cheaper models vs always gpt-4o
    total_savings_usd   : sum of both
    savings_pct         : percentage saved vs hypothetical all-gpt-4o baseline
    """
    return tel.get_total_savings()

