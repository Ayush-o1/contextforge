"""Context compressor — summarizes older turns to reduce token usage."""

from __future__ import annotations

import logging

import tiktoken

from app.config import Settings

logger = logging.getLogger(__name__)


def count_tokens(messages: list[dict], model: str = "gpt-3.5-turbo") -> int:
    """Count total tokens across all messages."""
    try:
        enc = tiktoken.encoding_for_model(model)
    except KeyError:
        enc = tiktoken.get_encoding("cl100k_base")  # fallback for unknown models

    total = 0
    for msg in messages:
        total += len(enc.encode(msg.get("content", ""))) + 4  # +4 for role overhead
    return total


async def compress_context(
    messages: list[dict],
    model: str,
    proxy_client,
    settings: Settings,
) -> tuple[list[dict], float]:
    """
    Summarize older turns if total tokens exceed threshold.
    Returns (messages, compression_ratio).
    Falls back to original messages on any error.
    """
    total_tokens = count_tokens(messages, model)

    # Don't compress if under threshold or conversation too short
    if total_tokens <= settings.compress_threshold:
        return messages, 1.0

    if len(messages) <= settings.compress_min_turns:
        return messages, 1.0

    # Split: keep system messages + recent turns verbatim, summarize the rest
    system_msgs = [m for m in messages if m["role"] == "system"]
    non_system = [m for m in messages if m["role"] != "system"]

    split_idx = max(1, len(non_system) - settings.compress_keep_recent)
    turns_to_summarize = non_system[:split_idx]
    recent_turns = non_system[split_idx:]

    if not turns_to_summarize:
        return messages, 1.0

    try:
        summary_prompt = (
            "Summarize the following conversation concisely, preserving all key facts, "
            "decisions, and context needed for future turns:\n\n"
            + "\n".join(
                f"{m['role'].upper()}: {m['content']}" for m in turns_to_summarize
            )
        )

        summary_text = await proxy_client.simple_completion(
            model=settings.compress_summary_model,
            prompt=summary_prompt,
        )

        summary_message = {
            "role": "user",
            "content": f"[SUMMARY OF EARLIER CONVERSATION]: {summary_text}",
        }

        compressed = system_msgs + [summary_message] + recent_turns
        ratio = count_tokens(compressed, model) / total_tokens

        logger.info(f"Context compressed: {total_tokens} → {count_tokens(compressed, model)} tokens (ratio: {ratio:.2f})")
        return compressed, ratio

    except Exception as e:
        logger.warning(f"Compression failed, proceeding uncompressed: {e}")
        return messages, 1.0