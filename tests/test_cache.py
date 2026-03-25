"""Unit and integration tests for the semantic cache.

All tests use mocked Redis and FAISS — no external services required.
"""

from __future__ import annotations

import json
import threading
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from app.cache import CacheResult, SemanticCache
from app.config import Settings
from app.vector_store import VectorStore

# ───────────────────────── VectorStore Tests ─────────────────────────────


class TestVectorStore:
    """Tests for the FAISS vector store wrapper."""

    def test_empty_search_returns_empty(self):
        """Searching an empty index returns no results."""
        store = VectorStore(dimension=384, index_path="/tmp/test_faiss.index")
        vector = np.random.randn(384).astype(np.float32)
        vector /= np.linalg.norm(vector)
        results = store.search(vector)
        assert results == []

    def test_add_and_search(self):
        """Adding a vector and searching for it returns a match."""
        store = VectorStore(dimension=384, index_path="/tmp/test_faiss.index")
        vector = np.random.randn(384).astype(np.float32)
        vector /= np.linalg.norm(vector)

        store.add(vector, "key1")
        results = store.search(vector, k=1)

        assert len(results) == 1
        assert results[0][0] == "key1"
        assert results[0][1] > 0.99  # same vector → similarity ~1.0

    def test_search_returns_most_similar(self):
        """Search returns the most similar vector, not just the first added."""
        store = VectorStore(dimension=384, index_path="/tmp/test_faiss.index")

        # Create two distinct vectors
        v1 = np.random.randn(384).astype(np.float32)
        v1 /= np.linalg.norm(v1)
        v2 = np.random.randn(384).astype(np.float32)
        v2 /= np.linalg.norm(v2)

        store.add(v1, "key_v1")
        store.add(v2, "key_v2")

        # Search for v1 → should return key_v1 with highest similarity
        results = store.search(v1, k=1)
        assert results[0][0] == "key_v1"

    def test_size_property(self):
        """Size property reflects the number of vectors added."""
        store = VectorStore(dimension=384, index_path="/tmp/test_faiss.index")
        assert store.size == 0

        v = np.random.randn(384).astype(np.float32)
        v /= np.linalg.norm(v)
        store.add(v, "key1")
        assert store.size == 1

    def test_reset_clears_index(self):
        """Reset clears all vectors from the store."""
        store = VectorStore(dimension=384, index_path="/tmp/test_faiss.index")
        v = np.random.randn(384).astype(np.float32)
        v /= np.linalg.norm(v)
        store.add(v, "key1")
        assert store.size == 1

        store.reset()
        assert store.size == 0

    def test_concurrent_writes_no_corruption(self):
        """10 simultaneous writes don't corrupt the FAISS index."""
        store = VectorStore(dimension=384, index_path="/tmp/test_faiss.index")
        errors = []

        def add_vector(idx):
            try:
                v = np.random.randn(384).astype(np.float32)
                v /= np.linalg.norm(v)
                store.add(v, f"key_{idx}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=add_vector, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert store.size == 10


# ──────────────────────── SemanticCache Tests ────────────────────────────


class TestSemanticCache:
    """Tests for the cache orchestrator."""

    @pytest.fixture
    def cache_settings(self) -> Settings:
        return Settings(
            openai_api_key="test",
            similarity_threshold=0.92,
            cache_ttl_seconds=86400,
        )

    @pytest.fixture
    def mock_embedder_for_cache(self) -> MagicMock:
        embedder = MagicMock()
        embedder.dimension = 384
        test_vector = np.ones(384, dtype=np.float32)
        test_vector /= np.linalg.norm(test_vector)
        embedder.embed.return_value = test_vector
        embedder.content_hash.return_value = "hash_abc"
        embedder.messages_to_text.return_value = "user: Hello!"
        return embedder

    @pytest.fixture
    def vector_store(self) -> VectorStore:
        store = VectorStore(dimension=384, index_path="/tmp/test_cache_faiss.index")
        store.reset()
        return store

    @pytest.fixture
    def mock_redis_client(self) -> AsyncMock:
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.set = AsyncMock()
        redis.close = AsyncMock()
        return redis

    @pytest.fixture
    def cache(self, mock_embedder_for_cache, vector_store, mock_redis_client, cache_settings) -> SemanticCache:
        return SemanticCache(
            embedder=mock_embedder_for_cache,
            vector_store=vector_store,
            redis=mock_redis_client,
            settings=cache_settings,
        )

    @pytest.mark.asyncio
    async def test_cache_miss_empty_index(self, cache):
        """Cache miss on empty index."""
        result = await cache.lookup("gpt-3.5-turbo", [{"role": "user", "content": "Hello"}])
        assert result.hit is False

    @pytest.mark.asyncio
    async def test_cache_store_and_hit(self, cache, mock_redis_client, chat_completion_fixture):
        """Store a response, then look it up — should hit."""
        messages = [{"role": "user", "content": "Hello"}]

        # Store
        await cache.store("gpt-3.5-turbo", messages, chat_completion_fixture)

        # Mock Redis to return the stored data
        mock_redis_client.get.return_value = json.dumps(chat_completion_fixture)

        # Lookup
        result = await cache.lookup("gpt-3.5-turbo", messages)
        assert result.hit is True
        assert result.response == chat_completion_fixture
        assert result.similarity_score > 0.99

    @pytest.mark.asyncio
    async def test_cache_miss_below_threshold(self, cache, vector_store, mock_embedder_for_cache):
        """Similar but below threshold → miss."""
        messages = [{"role": "user", "content": "Hello"}]

        # Add a vector to the store
        v1 = np.ones(384, dtype=np.float32)
        v1 /= np.linalg.norm(v1)
        vector_store.add(v1, "key1")

        # Now make embedder return a different vector for lookup
        v2 = np.random.randn(384).astype(np.float32)
        v2 /= np.linalg.norm(v2)
        mock_embedder_for_cache.embed.return_value = v2

        result = await cache.lookup("gpt-3.5-turbo", messages)
        # With random vector, similarity will be low → miss
        assert result.hit is False

    @pytest.mark.asyncio
    async def test_cache_miss_redis_expired(self, cache, mock_redis_client, chat_completion_fixture):
        """Vector exists in FAISS but Redis entry expired → miss."""
        messages = [{"role": "user", "content": "Hello"}]

        # Store to get vector in FAISS
        await cache.store("gpt-3.5-turbo", messages, chat_completion_fixture)

        # Redis returns None (TTL expired)
        mock_redis_client.get.return_value = None

        result = await cache.lookup("gpt-3.5-turbo", messages)
        assert result.hit is False

    @pytest.mark.asyncio
    async def test_store_calls_redis_with_ttl(self, cache, mock_redis_client, chat_completion_fixture):
        """Store writes to Redis with the configured TTL."""
        messages = [{"role": "user", "content": "Hello"}]
        await cache.store("gpt-3.5-turbo", messages, chat_completion_fixture)

        mock_redis_client.set.assert_called_once()
        call_kwargs = mock_redis_client.set.call_args
        assert call_kwargs[1]["ex"] == 86400  # TTL from settings


# ─────────────── Integration: Cache in Chat Endpoint ─────────────────────


class TestChatCompletionsWithCache:
    """Tests for the /v1/chat/completions endpoint with cache integration."""

    def test_cache_hit_returns_cached_response(
        self, test_client, mock_cache, chat_completion_fixture, sample_request_body
    ):
        """Cache hit returns the cached response with X-Cache: HIT header."""
        mock_cache.lookup.return_value = CacheResult(
            hit=True,
            response=chat_completion_fixture,
            similarity_score=0.95,
            cache_key="test_key",
        )

        resp = test_client.post("/v1/chat/completions", json=sample_request_body)
        assert resp.status_code == 200
        assert resp.headers.get("x-cache") == "HIT"
        assert resp.headers.get("x-similarity") == "0.95"
        assert resp.json()["id"] == "chatcmpl-abc123"

    def test_cache_miss_forwards_upstream(
        self, test_client, mock_cache, mock_proxy_client, chat_completion_fixture, sample_request_body
    ):
        """Cache miss forwards to upstream and returns X-Cache: MISS."""
        mock_cache.lookup.return_value = CacheResult(hit=False)
        mock_proxy_client.forward.return_value = chat_completion_fixture

        resp = test_client.post("/v1/chat/completions", json=sample_request_body)
        assert resp.status_code == 200
        assert resp.headers.get("x-cache") == "MISS"
        mock_proxy_client.forward.assert_called_once()
        mock_cache.store.assert_called_once()

    def test_streaming_bypasses_cache(
        self, test_client, mock_cache, mock_proxy_client, stream_chunks_fixture, sample_streaming_request_body
    ):
        """Streaming requests bypass the cache entirely."""

        async def mock_stream(request):
            for chunk in stream_chunks_fixture:
                yield f"data: {json.dumps(chunk)}\n\n"
            yield "data: [DONE]\n\n"

        mock_proxy_client.forward_stream = mock_stream

        resp = test_client.post("/v1/chat/completions", json=sample_streaming_request_body)
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        # Cache lookup should NOT have been called
        mock_cache.lookup.assert_not_called()
