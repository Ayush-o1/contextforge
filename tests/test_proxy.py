"""Integration tests for the proxy passthrough endpoint.

All tests use recorded fixtures — no live API calls.
"""

from __future__ import annotations

import json

from app.proxy import UpstreamError

# ───────────────────────── Health Check ──────────────────────────────────


class TestHealthCheck:
    """Tests for GET /health."""

    def test_health_returns_200(self, test_client):
        resp = test_client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["version"] == "0.6.0"


# ──────────────────── Non-Streaming Completions ──────────────────────────


class TestChatCompletionsNonStreaming:
    """Tests for POST /v1/chat/completions (stream=false)."""

    def test_successful_completion(
        self,
        test_client,
        mock_proxy_client,
        chat_completion_fixture,
        sample_request_body,
    ):
        """Verify passthrough returns the upstream response as-is."""
        mock_proxy_client.forward.return_value = chat_completion_fixture

        resp = test_client.post("/v1/chat/completions", json=sample_request_body)

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "chatcmpl-abc123"
        assert data["object"] == "chat.completion"
        assert data["choices"][0]["message"]["content"] == "Hello! How can I help you today?"
        assert data["usage"]["total_tokens"] == 18

        mock_proxy_client.forward.assert_called_once()

    def test_response_preserves_all_fields(
        self,
        test_client,
        mock_proxy_client,
        chat_completion_fixture,
        sample_request_body,
    ):
        """Verify no fields are dropped during passthrough."""
        mock_proxy_client.forward.return_value = chat_completion_fixture

        resp = test_client.post("/v1/chat/completions", json=sample_request_body)

        data = resp.json()
        assert data["model"] == "gpt-3.5-turbo-0125"
        assert data["system_fingerprint"] == "fp_abc123"
        assert data["choices"][0]["finish_reason"] == "stop"

    def test_missing_messages_returns_422(self, test_client):
        """Verify request validation rejects missing messages field."""
        resp = test_client.post(
            "/v1/chat/completions",
            json={"model": "gpt-3.5-turbo"},
        )
        assert resp.status_code == 422

    def test_missing_model_returns_422(self, test_client):
        """Verify request validation rejects missing model field."""
        resp = test_client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "Hi"}]},
        )
        assert resp.status_code == 422

    def test_extra_fields_forwarded(
        self,
        test_client,
        mock_proxy_client,
        chat_completion_fixture,
    ):
        """Verify extra fields in the request are preserved (extra='allow')."""
        mock_proxy_client.forward.return_value = chat_completion_fixture

        resp = test_client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": "Hi"}],
                "custom_field": "custom_value",
            },
        )
        assert resp.status_code == 200

        # Verify the proxy was called (the request made it through validation)
        mock_proxy_client.forward.assert_called_once()
        call_args = mock_proxy_client.forward.call_args[0][0]
        assert call_args.model == "gpt-3.5-turbo"


# ──────────────────────── Streaming Completions ──────────────────────────


class TestChatCompletionsStreaming:
    """Tests for POST /v1/chat/completions (stream=true)."""

    def test_streaming_response(
        self,
        test_client,
        mock_proxy_client,
        stream_chunks_fixture,
        sample_streaming_request_body,
    ):
        """Verify streaming returns SSE-formatted chunks."""

        async def mock_stream(request, model_override=None):
            for chunk in stream_chunks_fixture:
                yield f"data: {json.dumps(chunk)}\n\n"
            yield "data: [DONE]\n\n"

        mock_proxy_client.forward_stream = mock_stream

        resp = test_client.post(
            "/v1/chat/completions",
            json=sample_streaming_request_body,
        )

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")

        # Parse SSE lines
        body = resp.text
        lines = [line for line in body.strip().split("\n\n") if line.startswith("data:")]

        # 4 chunks + [DONE]
        assert len(lines) == 5
        assert lines[-1].strip() == "data: [DONE]"

        # Verify first content chunk
        first_chunk = json.loads(lines[0].replace("data: ", ""))
        assert first_chunk["object"] == "chat.completion.chunk"

    def test_streaming_headers(
        self,
        test_client,
        mock_proxy_client,
        stream_chunks_fixture,
        sample_streaming_request_body,
    ):
        """Verify correct SSE headers are set."""

        async def mock_stream(request, model_override=None):
            for chunk in stream_chunks_fixture:
                yield f"data: {json.dumps(chunk)}\n\n"
            yield "data: [DONE]\n\n"

        mock_proxy_client.forward_stream = mock_stream

        resp = test_client.post(
            "/v1/chat/completions",
            json=sample_streaming_request_body,
        )

        assert "text/event-stream" in resp.headers["content-type"]
        assert resp.headers.get("cache-control") == "no-cache"


# ────────────────────── Error Propagation ────────────────────────────────


class TestErrorPropagation:
    """Tests for upstream error handling."""

    def test_upstream_429_returns_429(
        self,
        test_client,
        mock_proxy_client,
        sample_request_body,
    ):
        """Verify upstream 429 is propagated to the caller."""
        mock_proxy_client.forward.side_effect = UpstreamError(
            status_code=429,
            detail="Rate limit exceeded",
        )

        resp = test_client.post("/v1/chat/completions", json=sample_request_body)

        assert resp.status_code == 429
        data = resp.json()
        assert "error" in data
        assert data["error"]["code"] == "429"

    def test_upstream_500_returns_500(
        self,
        test_client,
        mock_proxy_client,
        sample_request_body,
    ):
        """Verify upstream 500 is propagated."""
        mock_proxy_client.forward.side_effect = UpstreamError(
            status_code=500,
            detail="Internal server error",
        )

        resp = test_client.post("/v1/chat/completions", json=sample_request_body)

        assert resp.status_code == 500
        data = resp.json()
        assert data["error"]["type"] == "upstream_error"

    def test_upstream_502_returns_502(
        self,
        test_client,
        mock_proxy_client,
        sample_request_body,
    ):
        """Verify connection errors show as 502."""
        mock_proxy_client.forward.side_effect = UpstreamError(
            status_code=502,
            detail="Upstream connection error",
        )

        resp = test_client.post("/v1/chat/completions", json=sample_request_body)

        assert resp.status_code == 502

    def test_error_response_format(
        self,
        test_client,
        mock_proxy_client,
        sample_request_body,
    ):
        """Verify error responses follow OpenAI error format."""
        mock_proxy_client.forward.side_effect = UpstreamError(
            status_code=429,
            detail="Rate limit exceeded",
        )

        resp = test_client.post("/v1/chat/completions", json=sample_request_body)

        data = resp.json()
        assert "error" in data
        assert "message" in data["error"]
        assert "type" in data["error"]
        assert "code" in data["error"]
