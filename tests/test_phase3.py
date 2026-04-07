"""Phase 3 tests — cost tracking, request_log DB, and admin API endpoints.

All tests use in-memory or temp-file SQLite; no live API calls are made.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import Settings

# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _make_usage(prompt: int = 10, completion: int = 5):
    """Return a SimpleNamespace that mimics LiteLLM's usage object."""
    ns = SimpleNamespace()
    ns.prompt_tokens = prompt
    ns.completion_tokens = completion
    ns.total_tokens = prompt + completion
    return ns


def _make_completion_response(model: str = "openai/gpt-4o", prompt: int = 10, completion: int = 5):
    """Return a minimal object that mimics a LiteLLM ModelResponse."""
    rsp = SimpleNamespace()
    rsp.model = model
    rsp.usage = _make_usage(prompt, completion)
    rsp.choices = []
    return rsp


# ═══════════════════════════════════════════════════════════════════════════
# 1. request_log DB helpers
# ═══════════════════════════════════════════════════════════════════════════


class TestRequestLogDB:
    """Tests for the new telemetry helpers (init / write / read)."""

    @pytest.fixture(autouse=True)
    def _use_temp_db(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Redirect DB_PATH to a throw-away temp file per test."""
        db = str(tmp_path / "test_telemetry.db")
        monkeypatch.setattr("app.telemetry.DB_PATH", db)
        import app.telemetry as tel
        tel.init_db()
        self.tel = tel

    def test_init_request_log_creates_table(self, tmp_path):
        """init_request_log() must create the request_log table."""
        import app.telemetry as tel
        tel.init_request_log()
        with tel.get_conn() as conn:
            tables = [
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            ]
        assert "request_log" in tables

    def test_write_and_read_request_log(self):
        """write_request_log → get_request_log round-trip."""
        rid = str(uuid.uuid4())
        record = {
            "request_id": rid,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": "openai/gpt-4o",
            "provider": "openai",
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_cost": 0.00125,
            "user_id": "test-user",
            "latency_ms": 342.1,
            "status": "success",
        }
        self.tel.write_request_log(record)

        rows = self.tel.get_request_log()
        assert len(rows) == 1
        row = rows[0]
        assert row["request_id"] == rid
        assert row["model"] == "openai/gpt-4o"
        assert row["provider"] == "openai"
        assert row["prompt_tokens"] == 100
        assert row["completion_tokens"] == 50
        assert abs(row["total_cost"] - 0.00125) < 1e-9
        assert row["user_id"] == "test-user"
        assert row["status"] == "success"

    def test_duplicate_request_id_is_ignored(self):
        """Duplicate request_id must not raise; row count stays at 1."""
        rid = str(uuid.uuid4())
        base = {
            "request_id": rid,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": "openai/gpt-4o",
            "provider": "openai",
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_cost": 0.001,
            "user_id": None,
            "latency_ms": 100.0,
            "status": "success",
        }
        self.tel.write_request_log(base)
        self.tel.write_request_log(base)  # duplicate — must be silent

        rows = self.tel.get_request_log()
        assert len(rows) == 1

    def test_get_request_log_filter_by_model(self):
        """model= filter must return only matching rows."""
        for model in ("openai/gpt-4o", "groq/llama3-8b-8192", "openai/gpt-4o"):
            self.tel.write_request_log({
                "request_id": str(uuid.uuid4()),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "model": model,
                "provider": model.split("/")[0],
                "prompt_tokens": 5,
                "completion_tokens": 5,
                "total_cost": 0.001,
                "user_id": None,
                "latency_ms": 50.0,
                "status": "success",
            })

        rows = self.tel.get_request_log(model="openai/gpt-4o")
        assert len(rows) == 2
        assert all(r["model"] == "openai/gpt-4o" for r in rows)

    def test_get_usage_summary_totals(self):
        """get_usage_summary() must correctly aggregate tokens and cost."""
        for i in range(3):
            self.tel.write_request_log({
                "request_id": str(uuid.uuid4()),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "model": "openai/gpt-3.5-turbo",
                "provider": "openai",
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_cost": 0.0001,
                "user_id": None,
                "latency_ms": 200.0,
                "status": "success",
            })

        summary = self.tel.get_usage_summary()
        assert summary["total_requests"] == 3
        assert summary["total_prompt_tokens"] == 300
        assert summary["total_completion_tokens"] == 150
        assert summary["total_tokens"] == 450
        assert abs(summary["total_spend_usd"] - 0.0003) < 1e-7
        assert len(summary["by_model"]) == 1
        assert summary["by_model"][0]["model"] == "openai/gpt-3.5-turbo"


# ═══════════════════════════════════════════════════════════════════════════
# 2. LiteLLM success callback
# ═══════════════════════════════════════════════════════════════════════════


class TestLiteLLMCallback:
    """Tests for _litellm_success_callback in app/proxy.py."""

    @pytest.fixture(autouse=True)
    def _use_temp_db(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        db = str(tmp_path / "cb_test.db")
        monkeypatch.setattr("app.telemetry.DB_PATH", db)
        import app.telemetry as tel
        tel.init_db()
        self.tel = tel

    @pytest.mark.asyncio
    async def test_callback_writes_to_request_log(self, monkeypatch):
        """Callback must insert a row into request_log with correct fields."""
        from app.proxy import _litellm_success_callback

        call_id = str(uuid.uuid4())
        kwargs = {"model": "openai/gpt-4o", "litellm_call_id": call_id, "user": "alice"}
        response = _make_completion_response("openai/gpt-4o", prompt=50, completion=20)
        t0 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        t1 = datetime(2025, 1, 1, 12, 0, 1, tzinfo=timezone.utc)  # 1 second later

        with patch("litellm.completion_cost", return_value=0.00085):
            await _litellm_success_callback(kwargs, response, t0, t1)

        rows = self.tel.get_request_log()
        assert len(rows) == 1
        row = rows[0]
        assert row["request_id"] == call_id
        assert row["model"] == "openai/gpt-4o"
        assert row["provider"] == "openai"
        assert row["prompt_tokens"] == 50
        assert row["completion_tokens"] == 20
        assert abs(row["total_cost"] - 0.00085) < 1e-9
        assert row["user_id"] == "alice"
        assert abs(row["latency_ms"] - 1000.0) < 1.0  # ~1 second
        assert row["status"] == "success"

    @pytest.mark.asyncio
    async def test_callback_handles_missing_pricing(self, monkeypatch):
        """Callback must not crash if completion_cost() raises; cost defaults to 0."""
        from app.proxy import _litellm_success_callback

        kwargs = {"model": "unknown/model-x", "litellm_call_id": str(uuid.uuid4())}
        response = _make_completion_response("unknown/model-x")
        t0 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        t1 = datetime(2025, 1, 1, 12, 0, 0, 500000, tzinfo=timezone.utc)

        with patch("litellm.completion_cost", side_effect=Exception("no pricing")):
            await _litellm_success_callback(kwargs, response, t0, t1)

        rows = self.tel.get_request_log()
        assert len(rows) == 1
        assert rows[0]["total_cost"] == 0.0

    @pytest.mark.asyncio
    async def test_callback_provider_default_for_unprefixed_model(self):
        """Models without a / prefix must default provider to 'openai'."""
        from app.proxy import _litellm_success_callback

        kwargs = {"model": "gpt-3.5-turbo", "litellm_call_id": str(uuid.uuid4())}
        response = _make_completion_response("gpt-3.5-turbo")
        t0 = t1 = datetime(2025, 1, 1, tzinfo=timezone.utc)

        with patch("litellm.completion_cost", return_value=0.0001):
            await _litellm_success_callback(kwargs, response, t0, t1)

        rows = self.tel.get_request_log()
        assert rows[0]["provider"] == "openai"


# ═══════════════════════════════════════════════════════════════════════════
# 3. Cache cost = 0 scenario
# ═══════════════════════════════════════════════════════════════════════════


class TestCachedRequestCost:
    """Verify that cached requests produce zero spend in request_log.

    Because the LiteLLM callback only fires for real upstream calls,
    a cache hit will never insert a row into request_log. The usage
    summary for requests filtered to 'openai/gpt-4o' must therefore
    reflect the correct total that excludes those hits.
    """

    @pytest.fixture(autouse=True)
    def _use_temp_db(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        db = str(tmp_path / "cache_cost_test.db")
        monkeypatch.setattr("app.telemetry.DB_PATH", db)
        import app.telemetry as tel
        tel.init_db()
        self.tel = tel

    def test_only_real_calls_appear_in_request_log(self):
        """Cache hits (logged only in telemetry) must not inflate request_log cost."""
        # Simulate 2 real upstream calls
        for _ in range(2):
            self.tel.write_request_log({
                "request_id": str(uuid.uuid4()),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "model": "openai/gpt-4o",
                "provider": "openai",
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_cost": 0.001,
                "user_id": None,
                "latency_ms": 500.0,
                "status": "success",
            })

        # Simulate 3 cache hits written to the OLD telemetry table (by middleware)
        for _ in range(3):
            self.tel.write_record({
                "request_id": str(uuid.uuid4()),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "model_requested": "openai/gpt-4o",
                "model_used": "openai/gpt-4o",
                "cache_hit": True,
                "similarity_score": 0.97,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "estimated_cost_usd": 0.0,
                "latency_ms": 5.0,
                "compressed": False,
                "compression_ratio": 1.0,
            })

        summary = self.tel.get_usage_summary()
        # Only the 2 real calls must appear in request_log totals
        assert summary["total_requests"] == 2
        assert abs(summary["total_spend_usd"] - 0.002) < 1e-9
        # Cache hit rate is from telemetry table: 3 hits out of 3 total rows
        assert summary["cache_hit_rate"] == 1.0


# ═══════════════════════════════════════════════════════════════════════════
# 4. Admin API endpoint tests
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture()
def admin_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, test_settings: Settings):
    """TestClient wired against a temp SQLite DB, with mocked proxy/cache/router."""
    db = str(tmp_path / "admin_test.db")
    monkeypatch.setattr("app.telemetry.DB_PATH", db)

    import app.telemetry as tel
    tel.init_db()

    # Seed request_log with known rows
    for model, cost in [
        ("openai/gpt-4o", 0.005),
        ("openai/gpt-4o", 0.003),
        ("groq/llama3-8b-8192", 0.0001),
    ]:
        tel.write_request_log({
            "request_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": model,
            "provider": model.split("/")[0],
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_cost": cost,
            "user_id": None,
            "latency_ms": 300.0,
            "status": "success",
        })

    from app.cache import CacheResult
    from app.main import app
    from app.proxy import ProxyClient
    from app.router import ModelRouter, RoutingDecision, Tier

    mock_proxy = AsyncMock(spec=ProxyClient)
    mock_proxy.close = AsyncMock()
    mock_cache = AsyncMock()
    mock_cache.close = AsyncMock()
    mock_cache.lookup.return_value = CacheResult(hit=False)
    mock_router = MagicMock(spec=ModelRouter)
    mock_router.route.return_value = RoutingDecision(
        tier=Tier.SIMPLE,
        model_requested="gpt-3.5-turbo",
        model_selected="gpt-3.5-turbo",
        reason="test",
        token_count=2,
    )

    app.state.proxy_client = mock_proxy
    app.state.settings = test_settings
    app.state.cache = mock_cache
    app.state.router = mock_router

    return TestClient(app, raise_server_exceptions=False)


class TestAdminUsageEndpoint:
    """Tests for GET /admin/usage."""

    def test_usage_returns_200(self, admin_client):
        resp = admin_client.get("/admin/usage")
        assert resp.status_code == 200

    def test_usage_structure(self, admin_client):
        data = admin_client.get("/admin/usage").json()
        expected_keys = {
            "total_requests", "total_prompt_tokens", "total_completion_tokens",
            "total_tokens", "total_spend_usd", "avg_latency_ms",
            "cache_hit_rate", "by_model", "filters_applied",
        }
        assert expected_keys.issubset(data.keys())

    def test_usage_totals(self, admin_client):
        data = admin_client.get("/admin/usage").json()
        assert data["total_requests"] == 3
        # 3 rows × 150 tokens each = 450
        assert data["total_tokens"] == 450
        assert abs(data["total_spend_usd"] - 0.0081) < 1e-6

    def test_usage_model_filter(self, admin_client):
        data = admin_client.get("/admin/usage", params={"model": "openai/gpt-4o"}).json()
        assert data["total_requests"] == 2
        assert abs(data["total_spend_usd"] - 0.008) < 1e-6
        assert data["filters_applied"]["model"] == "openai/gpt-4o"

    def test_usage_by_model_breakdown(self, admin_client):
        data = admin_client.get("/admin/usage").json()
        models = [r["model"] for r in data["by_model"]]
        assert "openai/gpt-4o" in models
        assert "groq/llama3-8b-8192" in models

    def test_logs_endpoint_returns_200(self, admin_client):
        resp = admin_client.get("/admin/logs")
        assert resp.status_code == 200
        data = resp.json()
        assert "records" in data
        assert data["count"] == 3

    def test_logs_model_filter(self, admin_client):
        resp = admin_client.get("/admin/logs", params={"model": "groq/llama3-8b-8192"})
        data = resp.json()
        assert data["count"] == 1
        assert data["records"][0]["model"] == "groq/llama3-8b-8192"


# ═══════════════════════════════════════════════════════════════════════════
# 5. Config defaults
# ═══════════════════════════════════════════════════════════════════════════


class TestOtelConfigDefaults:
    """Verify OTel settings have safe defaults."""

    def test_enable_otel_defaults_to_false(self):
        s = Settings()
        assert s.enable_otel is False

    def test_otel_endpoint_default(self):
        s = Settings()
        assert s.otel_endpoint == "http://localhost:4317"

    def test_enable_otel_can_be_set_true(self):
        s = Settings(enable_otel=True, otel_endpoint="http://collector:4317")
        assert s.enable_otel is True
        assert s.otel_endpoint == "http://collector:4317"
