"""Upstream LLM forwarding logic using the openai-python SDK.

Handles both non-streaming and streaming (SSE) passthrough to OpenAI.
Supports model override from the router.
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator

from openai import APIConnectionError, APIError, APITimeoutError, AsyncOpenAI, RateLimitError

from app.config import Settings
from app.models import ChatCompletionRequest


class UpstreamError(Exception):
    """Raised when the upstream LLM API returns an error."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class ProxyClient:
    """Thin wrapper around the async OpenAI SDK for upstream forwarding."""

    def __init__(self, settings: Settings) -> None:
        self._client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )

    async def forward(self, request: ChatCompletionRequest, model_override: str | None = None) -> dict:
        """Forward a non-streaming request to OpenAI and return the raw response dict.

        Args:
            request: The validated chat completion request.
            model_override: If provided, use this model instead of the request's model.
        """
        try:
            payload = request.model_dump(exclude_none=True)
            payload["stream"] = False
            if model_override:
                payload["model"] = model_override

            response = await self._client.chat.completions.create(**payload)
            return response.model_dump()

        except RateLimitError as exc:
            raise UpstreamError(status_code=429, detail=str(exc)) from exc
        except APIConnectionError as exc:
            raise UpstreamError(status_code=502, detail=f"Upstream connection error: {exc}") from exc
        except APITimeoutError as exc:
            raise UpstreamError(status_code=504, detail=f"Upstream timeout: {exc}") from exc
        except APIError as exc:
            raise UpstreamError(
                status_code=exc.status_code or 500,
                detail=str(exc),
            ) from exc

    async def forward_stream(
        self, request: ChatCompletionRequest, model_override: str | None = None
    ) -> AsyncGenerator[str, None]:
        """Forward a streaming request and yield SSE-formatted strings.

        Args:
            request: The validated chat completion request.
            model_override: If provided, use this model instead of the request's model.
        """
        try:
            payload = request.model_dump(exclude_none=True)
            payload["stream"] = True
            if model_override:
                payload["model"] = model_override

            stream = await self._client.chat.completions.create(**payload)

            async for chunk in stream:
                data = chunk.model_dump()
                yield f"data: {json.dumps(data)}\n\n"

            yield "data: [DONE]\n\n"

        except RateLimitError as exc:
            raise UpstreamError(status_code=429, detail=str(exc)) from exc
        except APIConnectionError as exc:
            raise UpstreamError(status_code=502, detail=f"Upstream connection error: {exc}") from exc
        except APITimeoutError as exc:
            raise UpstreamError(status_code=504, detail=f"Upstream timeout: {exc}") from exc
        except APIError as exc:
            raise UpstreamError(
                status_code=exc.status_code or 500,
                detail=str(exc),
            ) from exc

    async def simple_completion(self, model: str, prompt: str) -> str:
        """Lightweight completion used internally by the compressor."""
        try:
            response = await self._client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                stream=False,
            )
            return response.choices[0].message.content
        except APIError as exc:
            raise UpstreamError(
                status_code=exc.status_code or 500,
                detail=str(exc),
            ) from exc

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.close()
