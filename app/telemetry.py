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

