"""Phase 5 tests — universal tool/function calling support.

Tests:
  - forward_with_tools() passes tools through to the router payload
  - Translation guard rejects ollama, huggingface, replicate providers
  - Requests without tools use the normal forward() path unaffected
  - get_total_savings() returns expected structure and math
  - GET /admin/savings endpoint returns 200 with correct fields
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models import ChatCompletionRequest
from app.proxy import _TOOL_UNSUPPORTED_PROVIDERS, ProxyClient, UpstreamError

# ─── Fixtures ─────────────────────────────────────────────────────────────

WEATHER_TOOL = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get current weather for a location.",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "City name"},
                "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
            },
            "required": ["location"],
        },
    },
}

_TOOL_RESPONSE = {
    "id": "chatcmpl-tools-abc",
    "object": "chat.completion",
    "created": 1700000000,
    "model": "openai/gpt-4o",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_abc123",
                        "type": "function",
                        "function": {"name": "get_weather", "arguments": '{"location":"London"}'},
                    }
                ],
            },
            "finish_reason": "tool_calls",
        }
    ],
    "usage": {"prompt_tokens": 80, "completion_tokens": 20, "total_tokens": 100},
}


def _make_tool_request(model: str = "gpt-4o") -> ChatCompletionRequest:
    return ChatCompletionRequest(
        model=model,
        messages=[{"role": "user", "content": "What's the weather in London?"}],
        tools=[WEATHER_TOOL],
    )


def _make_proxy(settings=None):
    """Return a ProxyClient with a fully mocked Router."""
    if settings is None:
        from app.config import Settings
        settings = Settings(openai_api_key="sk-test")
    client = ProxyClient.__new__(ProxyClient)
    client.settings = settings
    mock_router = MagicMock()
    mock_router.model_list = [
        {"model_name": "gpt-4o", "litellm_params": {"model": "openai/gpt-4o"}},
        {"model_name": "gpt-3.5-turbo", "litellm_params": {"model": "openai/gpt-3.5-turbo"}},
    ]
    client.router = mock_router
    return client


# ═══════════════════════════════════════════════════════════════════════════
# 1. Tool support constant
# ═══════════════════════════════════════════════════════════════════════════


def test_tool_unsupported_providers_is_frozenset():
    assert isinstance(_TOOL_UNSUPPORTED_PROVIDERS, frozenset)


def test_ollama_in_unsupported_providers():
    assert "ollama" in _TOOL_UNSUPPORTED_PROVIDERS
    assert "ollama_chat" in _TOOL_UNSUPPORTED_PROVIDERS


def test_openai_not_in_unsupported_providers():
    assert "openai" not in _TOOL_UNSUPPORTED_PROVIDERS


def test_anthropic_not_in_unsupported_providers():
    assert "anthropic" not in _TOOL_UNSUPPORTED_PROVIDERS


def test_gemini_not_in_unsupported_providers():
    assert "gemini" not in _TOOL_UNSUPPORTED_PROVIDERS


# ═══════════════════════════════════════════════════════════════════════════
# 2. forward_with_tools() — happy path
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_forward_with_tools_calls_router():
    """forward_with_tools() must delegate to router.acompletion with tool payload."""
    client = _make_proxy()
    mock_response = MagicMock()
    mock_response.model_dump.return_value = _TOOL_RESPONSE
    client.router.acompletion = AsyncMock(return_value=mock_response)

    req = _make_tool_request("gpt-4o")
    result = await client.forward_with_tools(req)

    assert result["choices"][0]["finish_reason"] == "tool_calls"
    tool_call = result["choices"][0]["message"]["tool_calls"][0]
    assert tool_call["function"]["name"] == "get_weather"

    # Verify tools were present in the upstream payload
    call_kwargs = client.router.acompletion.call_args[1]
    assert "tools" in call_kwargs


@pytest.mark.asyncio
async def test_forward_with_tools_no_tools_still_works():
    """forward_with_tools() without tools in the request must work as normal forward()."""
    client = _make_proxy()
    mock_response = MagicMock()
    mock_response.model_dump.return_value = {"choices": [{"message": {"content": "Hi"}}]}
    client.router.acompletion = AsyncMock(return_value=mock_response)

    req = ChatCompletionRequest(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Hi"}],
    )
    result = await client.forward_with_tools(req)
    assert "choices" in result


# ═══════════════════════════════════════════════════════════════════════════
# 3. Translation guard
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_translation_guard_rejects_ollama():
    """Tool requests to ollama/ models must raise UpstreamError(400)."""
    client = _make_proxy()
    # Register ollama model in the router so it resolves correctly
    client.router.model_list = [
        {"model_name": "ollama/llama3", "litellm_params": {"model": "ollama/llama3"}}
    ]
    req = _make_tool_request("ollama/llama3")
    with pytest.raises(UpstreamError) as exc_info:
        await client.forward_with_tools(req)
    assert exc_info.value.status_code == 400
    assert "ollama" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_translation_guard_rejects_huggingface():
    """Tool requests to huggingface/ models must raise UpstreamError(400)."""
    client = _make_proxy()
    client.router.model_list = []
    req = _make_tool_request("huggingface/gpt2")
    with pytest.raises(UpstreamError) as exc_info:
        await client.forward_with_tools(req)
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_translation_guard_allows_openai():
    """Tool requests to openai/ models must NOT be rejected by the guard."""
    client = _make_proxy()
    mock_response = MagicMock()
    mock_response.model_dump.return_value = _TOOL_RESPONSE
    client.router.acompletion = AsyncMock(return_value=mock_response)

    req = _make_tool_request("gpt-4o")
    result = await client.forward_with_tools(req)
    assert "choices" in result  # reached the upstream call, no guard raised


@pytest.mark.asyncio
async def test_translation_guard_allows_anthropic():
    """Tool requests to anthropic/ models must NOT be rejected by the guard."""
    from app.config import Settings
    settings = Settings(anthropic_api_key="sk-ant-test")
    client = _make_proxy(settings)
    client.router.model_list = [
        {"model_name": "claude-3-5-sonnet", "litellm_params": {"model": "anthropic/claude-3-5-sonnet-20241022"}}
    ]
    mock_response = MagicMock()
    mock_response.model_dump.return_value = _TOOL_RESPONSE
    client.router.acompletion = AsyncMock(return_value=mock_response)

    req = _make_tool_request("claude-3-5-sonnet")
    result = await client.forward_with_tools(req)
    assert "choices" in result


# ═══════════════════════════════════════════════════════════════════════════
# 4. get_total_savings()
# ═══════════════════════════════════════════════════════════════════════════


class TestTotalSavings:

    @pytest.fixture(autouse=True)
    def _temp_db(self, tmp_path: Path, monkeypatch):
        db = str(tmp_path / "savings_test.db")
        monkeypatch.setattr("app.telemetry.DB_PATH", db)
        import app.telemetry as tel
        tel.init_db()
        self.tel = tel

    def test_savings_returns_expected_keys(self):
        savings = self.tel.get_total_savings()
        expected = {
            "cache_savings_usd", "routing_savings_usd", "total_savings_usd",
            "cache_hits", "actual_spend_usd", "hypothetical_spend_usd", "savings_pct",
        }
        assert expected.issubset(savings.keys())

    def test_savings_zero_when_no_data(self):
        savings = self.tel.get_total_savings()
        assert savings["total_savings_usd"] == 0.0
        assert savings["cache_hits"] == 0
        assert savings["savings_pct"] == 0.0

    def test_cache_savings_calculated_correctly(self):
        """Cache hits in telemetry must produce non-zero cache_savings_usd."""
        self.tel.write_record({
            "request_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model_requested": "gpt-4o",
            "model_used": "openai/gpt-4o",
            "cache_hit": True,
            "similarity_score": 0.97,
            "prompt_tokens": 1_000_000,   # 1M prompt tokens → $5.00 at gpt-4o rates
            "completion_tokens": 0,
            "estimated_cost_usd": 0.0,
            "latency_ms": 5.0,
            "compressed": False,
            "compression_ratio": 1.0,
        })

        savings = self.tel.get_total_savings()
        assert savings["cache_hits"] == 1
        # 1M prompt tokens × $5/1M = $5.00
        assert abs(savings["cache_savings_usd"] - 5.0) < 0.001

    def test_routing_savings_positive_when_cheaper_model_used(self):
        """Routing to gpt-3.5-turbo instead of gpt-4o must produce positive routing savings."""
        # Write a real upstream call at gpt-3.5-turbo rates (~$0.0005 per 1M prompt tokens)
        self.tel.write_request_log({
            "request_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": "openai/gpt-3.5-turbo",
            "provider": "openai",
            "prompt_tokens": 1_000_000,   # 1M tokens
            "completion_tokens": 0,
            "total_cost": 0.50,           # gpt-3.5-turbo rate
            "user_id": None,
            "latency_ms": 300.0,
            "status": "success",
        })

        savings = self.tel.get_total_savings()
        # Hypothetical gpt-4o cost: $5.00. Actual: $0.50. Savings: $4.50
        assert savings["routing_savings_usd"] > 0
        assert savings["total_savings_usd"] > 0
        assert savings["savings_pct"] > 0

    def test_total_savings_is_sum_of_parts(self):
        """total_savings_usd must equal cache_savings + routing_savings."""
        savings = self.tel.get_total_savings()
        expected = round(savings["cache_savings_usd"] + savings["routing_savings_usd"], 6)
        assert abs(savings["total_savings_usd"] - expected) < 1e-9


# ═══════════════════════════════════════════════════════════════════════════
# 5. GET /admin/savings endpoint
# ═══════════════════════════════════════════════════════════════════════════


def test_admin_savings_endpoint(tmp_path, monkeypatch, test_client):
    """GET /admin/savings must return 200 with all expected fields."""
    db = str(tmp_path / "savings_ep_test.db")
    monkeypatch.setattr("app.telemetry.DB_PATH", db)
    import app.telemetry as tel
    tel.init_db()

    resp = test_client.get("/admin/savings")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_savings_usd" in data
    assert "cache_savings_usd" in data
    assert "routing_savings_usd" in data
    assert "savings_pct" in data
    assert isinstance(data["cache_hits"], int)
