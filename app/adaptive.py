"""Adaptive similarity threshold auto-tuning based on telemetry data.

Analyses recent cache hit rates from the telemetry SQLite database and
adjusts the similarity threshold up or down to optimise cache performance.

Rules:
  - hit_rate > 60 %  → threshold too loose  → raise by 0.01 (cap at max)
  - hit_rate < 20 %  → threshold too strict  → lower by 0.01 (floor at min)
  - otherwise        → no change
"""

from __future__ import annotations

import datetime
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any

import structlog

from app.config import Settings

logger = structlog.get_logger()

_lock = threading.Lock()

STEP = 0.01


class ThresholdManager:
    """Manages the adaptive similarity threshold backed by SQLite."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._ensure_table()

    # ── SQLite helpers ────────────────────────────────────────────────

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _ensure_table(self) -> None:
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS threshold_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    threshold REAL NOT NULL,
                    cache_hit_rate REAL NOT NULL,
                    evaluated_at TEXT NOT NULL
                )
            """)

    # ── Core logic ────────────────────────────────────────────────────

    def get_current(self, settings: Settings) -> float:
        """Return the latest adaptive threshold, or the static baseline."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT threshold FROM threshold_history ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if row is not None:
            return float(row["threshold"])
        return settings.similarity_threshold

    def evaluate(self, settings: Settings) -> dict[str, Any]:
        """Evaluate recent telemetry and adjust the threshold.

        Returns a dict with ``threshold``, ``cache_hit_rate``, and ``evaluated_at``.
        """
        window = settings.adaptive_threshold_window
        thr_min = settings.adaptive_threshold_min
        thr_max = settings.adaptive_threshold_max

        current = self.get_current(settings)

        # Read recent telemetry records
        cache_hit_rate = self._compute_hit_rate(window)

        new_threshold = current
        if cache_hit_rate > 0.60:
            new_threshold = min(current + STEP, thr_max)
        elif cache_hit_rate < 0.20:
            new_threshold = max(current - STEP, thr_min)

        new_threshold = round(new_threshold, 4)
        now = datetime.datetime.utcnow().isoformat()

        with _lock:
            with self._conn() as conn:
                conn.execute(
                    "INSERT INTO threshold_history (threshold, cache_hit_rate, evaluated_at) VALUES (?, ?, ?)",
                    (new_threshold, cache_hit_rate, now),
                )

        logger.info(
            "adaptive.evaluated",
            previous=current,
            new=new_threshold,
            cache_hit_rate=cache_hit_rate,
        )

        return {
            "threshold": new_threshold,
            "cache_hit_rate": round(cache_hit_rate, 4),
            "evaluated_at": now,
        }

    def get_info(self, settings: Settings) -> dict[str, Any]:
        """Return current threshold info for the API response."""
        current = self.get_current(settings)
        last_evaluated_at = self._last_evaluated_at()
        return {
            "current_threshold": current,
            "baseline": settings.similarity_threshold,
            "last_evaluated_at": last_evaluated_at,
        }

    # ── Private helpers ───────────────────────────────────────────────

    def _compute_hit_rate(self, window: int) -> float:
        """Compute cache hit rate from the telemetry table."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT cache_hit FROM telemetry ORDER BY id DESC LIMIT ?",
                (window,),
            ).fetchall()

        if not rows:
            return 0.0

        hits = sum(1 for r in rows if r["cache_hit"])
        return hits / len(rows)

    def _last_evaluated_at(self) -> str | None:
        """Return the timestamp of the most recent evaluation."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT evaluated_at FROM threshold_history ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return row["evaluated_at"] if row else None


def get_active_threshold(settings: Settings, manager: ThresholdManager | None) -> float:
    """Return the effective similarity threshold.

    Uses the adaptive value when the feature is enabled and a manager is
    available; otherwise falls back to the static config value.
    """
    if settings.adaptive_threshold_enabled and manager is not None:
        return manager.get_current(settings)
    return settings.similarity_threshold
