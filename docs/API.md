# ContextForge API Reference

> v0.7.0 — Complete endpoint documentation

---

## Base URL

```
http://localhost:8000
```

---

## Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/v1/chat/completions` | Chat completions (OpenAI-compatible) |
| `GET` | `/health` | Health check |
| `GET` | `/v1/telemetry` | Paginated telemetry records |
| `GET` | `/v1/telemetry/summary` | Aggregated telemetry statistics |
| `GET` | `/v1/threshold` | Current adaptive threshold info |
| `POST` | `/v1/threshold/evaluate` | Trigger threshold evaluation |
| `GET` | `/v1/cache/stats` | Cache statistics |
| `DELETE` | `/v1/cache` | Flush entire cache |
| `DELETE` | `/v1/cache/{key}` | Invalidate a specific cache entry |
| `GET` | `/dashboard` | Telemetry dashboard (HTML) |

---

## `POST /v1/chat/completions`

OpenAI-compatible chat completions endpoint. Supports both streaming and non-streaming requests.

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

| Header | Values | Description |
|--------|--------|-------------|
| `X-Cache-Hit` | `true` / `false` | Whether the response came from the semantic cache |
| `X-Model-Tier` | `simple` / `complex` | How the router classified the prompt |
| `X-Model-Selected` | e.g., `gpt-3.5-turbo`, `gpt-4o` | The model actually used for the upstream call |
| `X-Compressed` | `true` / `false` | Whether context compression was applied |
| `X-Compression-Ratio` | e.g., `0.65` | Ratio of compressed to original token count |

### Special Request Headers

| Header | Description |
|--------|-------------|
| `X-ContextForge-Model-Override` | Force a specific model, bypassing the router (e.g., `gpt-4o`) |
| `X-ContextForge-No-Compress` | Set to `true` to skip context compression for this request |

### Notes

- When `stream=true`, the response is returned as Server-Sent Events (SSE). Streaming requests bypass both caching and compression.
- On cache hit, no upstream API call is made — the cached response is returned directly with `X-Cache-Hit: true`.
- Upstream errors (429, 500, 502, etc.) are propagated to the client with the original status code and error body.

---

## `GET /health`

Health check endpoint. Returns the server status and version.

### Response

```json
{
  "status": "ok",
  "version": "0.7.0"
}
```

---

## `GET /v1/telemetry`

Returns paginated telemetry records, newest first. All data is stored locally in SQLite.

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

Returns aggregated telemetry statistics across all recorded requests.

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

### Field Descriptions

| Field | Description |
|-------|-------------|
| `total_requests` | Total number of recorded requests |
| `cache_hits` | Number of requests served from cache |
| `avg_latency_ms` | Average response latency in milliseconds |
| `total_cost_usd` | Estimated total cost (approximate — see note below) |
| `avg_tokens` | Average tokens per request |
| `cache_hit_rate` | Proportion of requests served from cache (0.0–1.0) |
| `p95_latency_ms` | 95th percentile latency |

> **Note:** Cost estimates use hardcoded per-token rates in `app/costs.py`. Actual billing from your LLM provider may differ.

---

## `GET /v1/threshold`

Returns the current adaptive similarity threshold and its metadata.

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

### How Evaluation Works

- Analyzes the most recent `ADAPTIVE_THRESHOLD_WINDOW` requests (default: 100)
- If cache hit rate > 60%: threshold is raised by 0.01 (up to `ADAPTIVE_THRESHOLD_MAX`)
- If cache hit rate < 20%: threshold is lowered by 0.01 (down to `ADAPTIVE_THRESHOLD_MIN`)
- Otherwise: threshold stays the same

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

> **Note:** If Redis is unavailable, `redis_keys` will return `0` and an error will be logged. The endpoint will not crash.

---

## `DELETE /v1/cache`

Flush the entire semantic cache. Clears all FAISS vectors and Redis cache keys. This operation is idempotent — calling it on an empty cache returns successfully.

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

Invalidate a specific cache entry by its key. Removes both the FAISS vector and the corresponding Redis entry.

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

---

## `GET /dashboard`

Serves the interactive telemetry dashboard. This is an HTML page that runs client-side with Chart.js and fetches data from the telemetry API endpoints.

- When accessed via the server (`http://localhost:8000/dashboard`), it shows live data.
- When opened directly from the filesystem (`docs/dashboard.html`), it runs in demo mode with sample data.
