"""SQLite telemetry writer and reader for per-request tracking."""

from __future__ import annotations

import dataclasses
import datetime
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from app.config import get_settings

DB_PATH = get_settings().sqlite_db_path
_lock = threading.Lock()


def _ensure_db_dir() -> None:
    """Ensure the database directory exists."""
    db_dir = Path(DB_PATH).parent
    db_dir.mkdir(parents=True, exist_ok=True)


def init_db() -> None:
    """Create telemetry table if it doesn't exist."""
    _ensure_db_dir()
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT UNIQUE,
                timestamp DATETIME,
                model_requested TEXT,
                model_used TEXT,
                cache_hit BOOLEAN,
                similarity_score REAL,
                prompt_tokens INTEGER,
                completion_tokens INTEGER,
                estimated_cost_usd REAL,
                latency_ms REAL,
                compressed BOOLEAN,
                compression_ratio REAL
            )
        """)
        conn.execute("PRAGMA journal_mode=WAL")
    # Also ensure the Phase-3 request_log table exists
    init_request_log()


@contextmanager
def get_conn():
    """Context manager for SQLite connections."""
    _ensure_db_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def write_record(record: dict[str, Any]) -> None:
    """Write a single telemetry record."""
    with _lock:
        try:
            with get_conn() as conn:
                conn.execute("""
                    INSERT OR IGNORE INTO telemetry
                    (request_id, timestamp, model_requested, model_used, cache_hit,
                     similarity_score, prompt_tokens, completion_tokens,
                     estimated_cost_usd, latency_ms, compressed, compression_ratio)
                    VALUES
                    (:request_id, :timestamp, :model_requested, :model_used, :cache_hit,
                     :similarity_score, :prompt_tokens, :completion_tokens,
                     :estimated_cost_usd, :latency_ms, :compressed, :compression_ratio)
                """, record)
        except Exception:
            pass


def get_records(limit: int = 50, offset: int = 0) -> list[dict]:
    """Return paginated telemetry records, newest first."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM telemetry ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return [dict(r) for r in rows]


def get_summary() -> dict[str, Any]:
    """Return aggregated telemetry stats."""
    with get_conn() as conn:
        row = conn.execute("""
            SELECT
                COUNT(*) as total_requests,
                SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END) as cache_hits,
                ROUND(AVG(latency_ms), 2) as avg_latency_ms,
                ROUND(SUM(estimated_cost_usd), 6) as total_cost_usd,
                ROUND(AVG(prompt_tokens + completion_tokens), 1) as avg_tokens
            FROM telemetry
        """).fetchone()

        p95_row = conn.execute("""
            SELECT latency_ms FROM telemetry
            ORDER BY latency_ms
            LIMIT 1 OFFSET (SELECT CAST(COUNT(*) * 0.95 AS INT) FROM telemetry)
        """).fetchone()

    summary = dict(row)
    total = summary["total_requests"] or 1
    summary["cache_hit_rate"] = round((summary["cache_hits"] or 0) / total, 4)
    summary["p95_latency_ms"] = p95_row["latency_ms"] if p95_row else None
    return summary


# ─── OOP wrappers ─────────────────────────────────────────────────────────


@dataclasses.dataclass
class TelemetryRecord:
    """Structured telemetry record that converts to a dict for write_record."""

    request_id: str
    timestamp: datetime.datetime
    model_requested: str
    model_used: str
    cache_hit: bool
    similarity_score: float
    prompt_tokens: int
    completion_tokens: int
    estimated_cost_usd: float
    latency_ms: float
    compressed: bool
    compression_ratio: float

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


class TelemetryDB:
    """OOP wrapper around the module-level telemetry functions."""

    def init_db(self) -> None:
        init_db()

    def write(self, record: TelemetryRecord | dict[str, Any]) -> None:
        if isinstance(record, TelemetryRecord):
            write_record(record.to_dict())
        else:
            write_record(record)

    def get_recent(self, limit: int = 50, offset: int = 0) -> list[dict]:
        return get_records(limit, offset)

    def get_summary(self) -> dict[str, Any]:
        return get_summary()


# ═══════════════════════════════════════════════════════════════════════════
# Phase 3 — request_log table (LiteLLM callback-driven, accurate cost data)
# ═══════════════════════════════════════════════════════════════════════════

_REQUEST_LOG_COLS = (
    "request_id", "timestamp", "model", "provider",
    "prompt_tokens", "completion_tokens", "total_cost",
    "user_id", "latency_ms", "status",
)


def init_request_log() -> None:
    """Create the request_log table if it doesn't exist.

    This table is populated exclusively by the LiteLLM success callback
    (see app/proxy.py).  Cached requests (which never reach LiteLLM) will
    NOT appear here — their cost is correctly zero.
    """
    _ensure_db_dir()
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS request_log (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id       TEXT    UNIQUE,
                timestamp        DATETIME NOT NULL,
                model            TEXT,
                provider         TEXT,
                prompt_tokens    INTEGER DEFAULT 0,
                completion_tokens INTEGER DEFAULT 0,
                total_cost       REAL    DEFAULT 0.0,
                user_id          TEXT,
                latency_ms       REAL,
                status           TEXT    DEFAULT 'success'
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_rl_timestamp ON request_log(timestamp)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_rl_model ON request_log(model)"
        )


def write_request_log(record: dict[str, Any]) -> None:
    """Thread-safe insert into request_log.  Silently ignores duplicates."""
    with _lock:
        try:
            _ensure_db_dir()
            with get_conn() as conn:
                conn.execute("""
                    INSERT OR IGNORE INTO request_log
                    (request_id, timestamp, model, provider,
                     prompt_tokens, completion_tokens, total_cost,
                     user_id, latency_ms, status)
                    VALUES
                    (:request_id, :timestamp, :model, :provider,
                     :prompt_tokens, :completion_tokens, :total_cost,
                     :user_id, :latency_ms, :status)
                """, {col: record.get(col) for col in _REQUEST_LOG_COLS})
        except Exception:
            pass


def get_request_log(
    limit: int = 50,
    offset: int = 0,
    model: str | None = None,
    status: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    user_id: str | None = None,
) -> list[dict]:
    """Return paginated request_log rows with optional filters."""
    clauses: list[str] = []
    params: list[Any] = []

    if model:
        clauses.append("model = ?")
        params.append(model)
    if status:
        clauses.append("status = ?")
        params.append(status)
    if start_date:
        clauses.append("timestamp >= ?")
        params.append(start_date)
    if end_date:
        clauses.append("timestamp <= ?")
        params.append(end_date)
    if user_id:
        clauses.append("user_id = ?")
        params.append(user_id)

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    params.extend([limit, offset])

    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM request_log {where} ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
    return [dict(r) for r in rows]


def get_usage_summary(
    model: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Return aggregated spend/token/latency summary from request_log.

    Also cross-references the telemetry table to compute the overall
    cache hit rate (cache hits never appear in request_log).
    """
    clauses: list[str] = []
    params: list[Any] = []

    if model:
        clauses.append("model = ?")
        params.append(model)
    if start_date:
        clauses.append("timestamp >= ?")
        params.append(start_date)
    if end_date:
        clauses.append("timestamp <= ?")
        params.append(end_date)
    if user_id:
        clauses.append("user_id = ?")
        params.append(user_id)

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

    with get_conn() as conn:
        row = conn.execute(f"""
            SELECT
                COUNT(*)                                     AS total_requests,
                COALESCE(SUM(prompt_tokens),    0)           AS total_prompt_tokens,
                COALESCE(SUM(completion_tokens),0)           AS total_completion_tokens,
                COALESCE(SUM(prompt_tokens + completion_tokens), 0) AS total_tokens,
                ROUND(COALESCE(SUM(total_cost), 0), 6)       AS total_spend_usd,
                ROUND(AVG(latency_ms), 2)                    AS avg_latency_ms
            FROM request_log {where}
        """, params).fetchone()

        # Per-model breakdown
        per_model = conn.execute(f"""
            SELECT
                model,
                COUNT(*)                                        AS requests,
                ROUND(COALESCE(SUM(total_cost), 0), 6)          AS spend_usd,
                COALESCE(SUM(prompt_tokens + completion_tokens), 0) AS total_tokens
            FROM request_log {where}
            GROUP BY model
            ORDER BY spend_usd DESC
        """, params).fetchall()

        # Cache hit rate from the existing telemetry table (broader scope)
        tel_row = conn.execute("""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END) AS hits
            FROM telemetry
        """).fetchone()

    summary = dict(row)
    summary["by_model"] = [dict(r) for r in per_model]

    tel = dict(tel_row)
    total_tel = tel["total"] or 1
    summary["cache_hit_rate"] = round((tel["hits"] or 0) / total_tel, 4)

    return summary


# ═══════════════════════════════════════════════════════════════════════════
# Phase 5 — Total savings calculator
# ═══════════════════════════════════════════════════════════════════════════

# Reference pricing used for savings estimation (per 1M tokens, USD)
_GPT4O_PROMPT_COST_PER_TOKEN = 5.00 / 1_000_000      # $5.00 / 1M
_GPT4O_COMPLETION_COST_PER_TOKEN = 15.00 / 1_000_000  # $15.00 / 1M


def get_total_savings() -> dict[str, Any]:
    """Calculate total cost savings across all tracked requests.

    Two savings streams are measured:

    1. **Cache Savings** — requests served from cache cost $0 in upstream API
       calls.  We estimate what they *would* have cost at gpt-4o rates
       (conservative upper-bound) using token counts from the telemetry table.

    2. **Routing Savings** — requests routed to a cheaper model (simple-tier)
       instead of gpt-4o.  We compare actual spend (from request_log, which
       uses litellm.completion_cost()) against the hypothetical gpt-4o cost
       for the same token counts.

    Returns
    -------
    dict with keys:
        cache_savings_usd        : float — cost avoided via cache hits
        routing_savings_usd      : float — cost avoided by routing to cheaper models
        total_savings_usd        : float — sum of both
        cache_hits               : int   — number of requests served from cache
        actual_spend_usd         : float — real money paid (from request_log)
        hypothetical_spend_usd   : float — what it would have cost at gpt-4o rates
        savings_pct              : float — percentage saved vs hypothetical
    """
    with get_conn() as conn:
        # --- Cache savings from the telemetry table ---
        cache_row = conn.execute("""
            SELECT
                SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END)          AS cache_hits,
                SUM(CASE WHEN cache_hit THEN prompt_tokens ELSE 0 END)     AS cached_prompt_tokens,
                SUM(CASE WHEN cache_hit THEN completion_tokens ELSE 0 END) AS cached_completion_tokens
            FROM telemetry
        """).fetchone()

        # --- Actual spend and token counts from request_log ---
        log_row = conn.execute("""
            SELECT
                COALESCE(SUM(total_cost), 0)         AS actual_spend_usd,
                COALESCE(SUM(prompt_tokens), 0)      AS total_prompt_tokens,
                COALESCE(SUM(completion_tokens), 0)  AS total_completion_tokens
            FROM request_log
        """).fetchone()

    cache = dict(cache_row)
    log = dict(log_row)

    # Cache savings: what those hit requests would have cost at gpt-4o rates
    cached_prompt = cache.get("cached_prompt_tokens") or 0
    cached_completion = cache.get("cached_completion_tokens") or 0
    cache_savings = (
        cached_prompt * _GPT4O_PROMPT_COST_PER_TOKEN
        + cached_completion * _GPT4O_COMPLETION_COST_PER_TOKEN
    )

    # Routing savings: hypothetical gpt-4o cost vs actual spend on cheaper models
    actual_prompt = log.get("total_prompt_tokens") or 0
    actual_completion = log.get("total_completion_tokens") or 0
    hypothetical_spend = (
        actual_prompt * _GPT4O_PROMPT_COST_PER_TOKEN
        + actual_completion * _GPT4O_COMPLETION_COST_PER_TOKEN
    )
    actual_spend = log.get("actual_spend_usd") or 0.0
    routing_savings = max(0.0, hypothetical_spend - actual_spend)

    total_savings = cache_savings + routing_savings
    total_hypothetical = cache_savings + hypothetical_spend
    savings_pct = round(total_savings / total_hypothetical * 100, 1) if total_hypothetical > 0 else 0.0

    return {
        "cache_savings_usd": round(cache_savings, 6),
        "routing_savings_usd": round(routing_savings, 6),
        "total_savings_usd": round(total_savings, 6),
        "cache_hits": cache.get("cache_hits") or 0,
        "actual_spend_usd": round(actual_spend, 6),
        "hypothetical_spend_usd": round(total_hypothetical, 6),
        "savings_pct": savings_pct,
    }
