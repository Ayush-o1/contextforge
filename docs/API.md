# ContextForge API Reference

> v0.7.0 — All endpoints documented

---

## Base URL

```
http://localhost:8000
```

---

## `POST /v1/chat/completions`

OpenAI-compatible chat completions endpoint. Supports both streaming and non-streaming.

### Request Body

```json
{
  "model": "gpt-3.5-turbo",
  "messages": [
    {"role": "user", "content": "What is the capital of France?"}
  ],
  "temperature": 0.7,
  "stream": false
}
```

### Response (non-streaming)

```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1700000000,
  "model": "gpt-3.5-turbo-0125",
  "choices": [
    {
      "index": 0,
      "message": {"role": "assistant", "content": "The capital of France is Paris."},
      "finish_reason": "stop"
    }
  ],
  "usage": {"prompt_tokens": 14, "completion_tokens": 8, "total_tokens": 22}
}
```

### Response Headers

| Header | Description |
|--------|-------------|
| `X-Cache` | `HIT` or `MISS` |
| `X-Similarity` | Cosine similarity score (on cache hit) |
| `X-Model-Tier` | Classification result: `simple` or `complex` |
| `X-Model-Selected` | The model actually used for the upstream call |
| `X-Compressed` | `True` if context compression was applied |
| `X-Compression-Ratio` | Ratio of compressed to original tokens (e.g. `0.65`) |

### Special Request Headers

| Header | Description |
|--------|-------------|
| `X-ContextForge-Model-Override` | Force a specific model, bypassing the router (e.g. `gpt-4o`) |
| `X-ContextForge-No-Compress` | Set to `true` to skip context compression for this request |

---

## `GET /health`

Health check endpoint.

### Response

```json
{
  "status": "ok",
  "version": "0.7.0"
}
```

---

## `GET /v1/telemetry`

Returns paginated telemetry records, newest first.

### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 50 | Maximum records to return |
| `offset` | int | 0 | Number of records to skip |

### Response

```json
{
  "records": [
    {
      "request_id": "abc-123",
      "timestamp": "2026-03-27T02:00:00",
      "model_requested": "gpt-3.5-turbo",
      "model_used": "gpt-3.5-turbo",
      "cache_hit": false,
      "similarity_score": 0.0,
      "prompt_tokens": 14,
      "completion_tokens": 8,
      "estimated_cost_usd": 0.000029,
      "latency_ms": 450.0,
      "compressed": false,
      "compression_ratio": 1.0
    }
  ],
  "limit": 50,
  "offset": 0
}
```

---

## `GET /v1/telemetry/summary`

Returns aggregated telemetry statistics.

### Response

```json
{
  "total_requests": 150,
  "cache_hits": 42,
  "avg_latency_ms": 320.5,
  "total_cost_usd": 0.0245,
  "avg_tokens": 35.2,
  "cache_hit_rate": 0.28,
  "p95_latency_ms": 890.0
}
```

---

## `GET /v1/threshold`

Returns the current adaptive similarity threshold info.

### Response

```json
{
  "current_threshold": 0.93,
  "baseline": 0.92,
  "last_evaluated_at": "2026-03-27T12:00:00"
}
```

---

## `POST /v1/threshold/evaluate`

Manually triggers an adaptive threshold evaluation based on recent cache hit rates.

### Response

```json
{
  "threshold": 0.93,
  "cache_hit_rate": 0.65,
  "evaluated_at": "2026-03-27T12:00:00"
}
```

---

## `GET /v1/cache/stats`

Returns cache statistics including vector count, Redis key count, and current similarity threshold.

### Response

```json
{
  "total_vectors": 150,
  "redis_keys": 148,
  "similarity_threshold": 0.93
}
```

---

## `DELETE /v1/cache`

Flush the entire semantic cache. Clears all FAISS vectors and Redis cache keys. Idempotent.

### Response

```json
{
  "status": "ok",
  "vectors_cleared": 150,
  "redis_keys_cleared": 148
}
```

---

## `DELETE /v1/cache/{key}`

Invalidate a specific cache entry by its key. Removes both the FAISS vector and Redis entry.

### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `key` | string | The cache key to invalidate |

### Response

```json
{
  "status": "ok",
  "key": "abc123",
  "removed": true
}
```
