"""Tests for the cache invalidation API.

All tests use mocked Redis and in-memory FAISS — no live services required.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from app.cache import SemanticCache
from app.config import Settings
from app.vector_store import VectorStore

# ── Helpers ──────────────────────────────────────────────────────────────


def _make_settings(**overrides) -> Settings:
    defaults = {
        "openai_api_key": "test",
        "similarity_threshold": 0.92,
        "cache_ttl_seconds": 86400,
    }
    defaults.update(overrides)
    return Settings(**defaults)


# ── VectorStore Tests ────────────────────────────────────────────────────


class TestVectorStoreFlush:
    """Tests for VectorStore.flush()."""

    def test_vector_store_flush_resets_index(self):
        """VectorStore.flush() resets the index to 0 vectors."""
        store = VectorStore(dimension=384, index_path="/tmp/test_flush_faiss.index")
        v = np.random.randn(384).astype(np.float32)
        v /= np.linalg.norm(v)
        store.add(v, "key1")
        store.add(v, "key2")
        assert store.size == 2

        cleared = store.flush()
        assert cleared == 2
        assert store.size == 0


# ── Cache Invalidation Tests ─────────────────────────────────────────────


class TestCacheInvalidation:
    """Tests for SemanticCache invalidate/flush/stats."""

    @pytest.fixture
    def mock_embedder(self) -> MagicMock:
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
        store = VectorStore(dimension=384, index_path="/tmp/test_invalidation_faiss.index")
        store.reset()
        return store

    @pytest.fixture
    def mock_redis(self) -> AsyncMock:
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.set = AsyncMock()
        redis.delete = AsyncMock(return_value=1)
        redis.scan = AsyncMock(return_value=(0, []))
        redis.close = AsyncMock()
        return redis

    @pytest.fixture
    def cache(self, mock_embedder, vector_store, mock_redis) -> SemanticCache:
        settings = _make_settings()
        return SemanticCache(
            embedder=mock_embedder,
            vector_store=vector_store,
            redis=mock_redis,
            settings=settings,
        )

    @pytest.mark.asyncio
    async def test_cache_invalidate_key(self, cache, mock_redis, vector_store, mock_embedder):
        """DELETE /v1/cache/{key} removes that key from Redis and FAISS."""
        # Store something first
        messages = [{"role": "user", "content": "Hello"}]
        cache_key = await cache.store("gpt-3.5-turbo", messages, {"response": "test"})

        assert vector_store.size == 1

        # Invalidate
        removed = await cache.invalidate(cache_key)
        assert removed is True
        mock_redis.delete.assert_called_once_with(f"cache:{cache_key}")
        assert vector_store.size == 0

    @pytest.mark.asyncio
    async def test_cache_flush_clears_all(self, cache, vector_store, mock_redis):
        """flush() clears all vectors and Redis keys."""
        # Add some vectors
        v = np.ones(384, dtype=np.float32)
        v /= np.linalg.norm(v)
        vector_store.add(v, "key1")
        vector_store.add(v, "key2")

        # Mock redis.scan to return keys then stop
        mock_redis.scan = AsyncMock(
            side_effect=[(0, [b"cache:key1", b"cache:key2"])]
        )

        result = await cache.flush()
        assert result["vectors_cleared"] == 2
        assert result["redis_keys_cleared"] == 2
        assert vector_store.size == 0

    @pytest.mark.asyncio
    async def test_cache_flush_is_idempotent(self, cache, mock_redis):
        """Double-flush doesn't crash and returns zeros on second call."""
        # First flush (empty cache)
        result1 = await cache.flush()
        assert result1["vectors_cleared"] == 0

        # Second flush — should still succeed
        result2 = await cache.flush()
        assert result2["vectors_cleared"] == 0

    @pytest.mark.asyncio
    async def test_cache_stats(self, cache, vector_store, mock_redis):
        """stats() returns vector and Redis key counts."""
        v = np.ones(384, dtype=np.float32)
        v /= np.linalg.norm(v)
        vector_store.add(v, "key1")

        # Mock redis.scan to return 1 key
        mock_redis.scan = AsyncMock(side_effect=[(0, [b"cache:key1"])])

        stats = await cache.stats()
        assert stats["total_vectors"] == 1
        assert stats["redis_keys"] == 1


# ── Endpoint Tests ───────────────────────────────────────────────────────


class TestCacheEndpoints:
    """Tests for cache invalidation endpoints via TestClient."""

    @pytest.fixture
    def cache_client(self, tmp_path):
        """Create a TestClient with mocked cache supporting stats/flush."""
        from fastapi.testclient import TestClient

        from app.adaptive import ThresholdManager
        from app.main import app
        from app.router import RoutingDecision, Tier

        db_path = str(tmp_path / "cache_endpoint_test.db")

        settings = _make_settings(sqlite_db_path=db_path)
        manager = ThresholdManager(db_path)

        mock_proxy = AsyncMock()
        mock_proxy.close = AsyncMock()

        mock_cache = AsyncMock()
        mock_cache.close = AsyncMock()
        mock_cache.stats = AsyncMock(return_value={"total_vectors": 5, "redis_keys": 3})
        mock_cache.flush = AsyncMock(return_value={"vectors_cleared": 5, "redis_keys_cleared": 3})
        mock_cache.invalidate = AsyncMock(return_value=True)

        mock_router = MagicMock()
        mock_router.route.return_value = RoutingDecision(
            tier=Tier.SIMPLE, model_requested="gpt-3.5-turbo",
            model_selected="gpt-3.5-turbo", reason="test", token_count=2,
        )

        app.state.settings = settings
        app.state.threshold_manager = manager
        app.state.proxy_client = mock_proxy
        app.state.cache = mock_cache
        app.state.router = mock_router

        return TestClient(app, raise_server_exceptions=False)

    def test_cache_stats_endpoint(self, cache_client):
        """GET /v1/cache/stats returns correct schema."""
        resp = cache_client.get("/v1/cache/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_vectors" in data
        assert "redis_keys" in data
        assert "similarity_threshold" in data
        assert data["total_vectors"] == 5
        assert data["redis_keys"] == 3

    def test_cache_flush_endpoint(self, cache_client):
        """DELETE /v1/cache clears vectors and returns counts."""
        resp = cache_client.delete("/v1/cache")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "vectors_cleared" in data
        assert "redis_keys_cleared" in data
