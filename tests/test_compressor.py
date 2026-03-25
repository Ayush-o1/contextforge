from unittest.mock import AsyncMock, MagicMock

import pytest

from app.compressor import compress_context, count_tokens


def make_messages(n: int) -> list[dict]:
    msgs = []
    for i in range(n):
        msgs.append({"role": "user", "content": f"Question number {i} about something interesting and detailed"})
        msgs.append({"role": "assistant", "content": f"Answer number {i} with a detailed and thorough response"})
    return msgs


def make_settings(threshold=500, keep_recent=4, min_turns=6):
    s = MagicMock()
    s.compress_threshold = threshold
    s.compress_keep_recent = keep_recent
    s.compress_min_turns = min_turns
    s.compress_summary_model = "gpt-3.5-turbo"
    return s


# ── Test 1 ────────────────────────────────────────────────────────────────
def test_token_counting_returns_positive():
    msgs = [{"role": "user", "content": "Hello world"}]
    assert count_tokens(msgs) > 0


# ── Test 2 ────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_no_compression_below_min_turns():
    messages = make_messages(2)  # 4 messages, below min_turns=6
    mock_client = MagicMock()
    settings = make_settings()

    result, ratio = await compress_context(messages, "gpt-3.5-turbo", mock_client, settings)

    assert result == messages
    assert ratio == 1.0


# ── Test 3 ────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_compression_reduces_message_count():
    messages = make_messages(10)
    mock_client = MagicMock()
    mock_client.simple_completion = AsyncMock(return_value="Summary of earlier conversation.")
    settings = make_settings(threshold=100)  # low threshold to trigger compression

    result, ratio = await compress_context(messages, "gpt-3.5-turbo", mock_client, settings)

    assert len(result) < len(messages)
    assert ratio < 1.0


# ── Test 4 ────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_fallback_on_error_returns_original():
    messages = make_messages(10)
    mock_client = MagicMock()
    mock_client.simple_completion = AsyncMock(side_effect=Exception("API down"))
    settings = make_settings(threshold=100)

    result, ratio = await compress_context(messages, "gpt-3.5-turbo", mock_client, settings)

    assert result == messages
    assert ratio == 1.0


# ── Test 5 ────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_system_messages_preserved():
    messages = [{"role": "system", "content": "You are a helpful assistant."}]
    messages += make_messages(10)
    mock_client = MagicMock()
    mock_client.simple_completion = AsyncMock(return_value="Summary.")
    settings = make_settings(threshold=100)

    result, ratio = await compress_context(messages, "gpt-3.5-turbo", mock_client, settings)

    assert result[0]["role"] == "system"
    assert result[0]["content"] == "You are a helpful assistant."
