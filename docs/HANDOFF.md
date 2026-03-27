# ContextForge — Developer Handoff

> For the next developer picking up from Phase 6 onwards.

---

## Project State

| Item | Value |
|------|-------|
| **Last completed phase** | Phase 5 (Telemetry Layer) |
| **Version** | `v0.5.0` |
| **Tests** | 54/54 passing |
| **Lint** | ruff clean (zero errors) |
| **Branch** | `main` has all phases merged |
| **Tags** | `v0.1.0` (Phase 1), `v0.2.0` (Phase 2), `v0.3.0` (Phase 3), `v0.4.0` (Phase 4), `v0.5.0` (Phase 5) |

---

## What Works Right Now

1. **`POST /v1/chat/completions`** — Full OpenAI-compatible endpoint
2. **Semantic caching** — FAISS + Redis, cosine similarity ≥0.92 threshold
3. **Model routing** — Rule-based classifier routes simple→gpt-3.5-turbo, complex→gpt-4o
4. **Context compression** — Long conversations automatically summarized to reduce token usage
5. **Telemetry** — Per-request metrics logged to SQLite (model, latency, cost, cache hit, compression)
6. **Streaming** — SSE passthrough works (but bypasses cache and compression)
7. **Error propagation** — Upstream 4xx/5xx errors surface correctly to the caller
8. **`GET /health`** — Returns `{"status":"ok","version":"0.5.0"}`
9. **`GET /v1/telemetry`** — Paginated telemetry records
10. **`GET /v1/telemetry/summary`** — Aggregated stats (cache hit rate, avg latency, total cost)

---

## Known Gotchas

### 1. `get_settings()` uses `@lru_cache`

Settings are loaded once from `.env` and cached for the process lifetime. If you change env vars at runtime, they won't take effect until restart. To force reload during tests:

```python
from app.config import get_settings
get_settings.cache_clear()
```

### 2. FAISS `_id_map` persisted as `.idmap`

The FAISS index and its ID map are two separate files:
- `data/faiss.index` — the vector index
- `data/faiss.index.idmap` — JSON mapping index positions → cache keys

**Both files must be moved, deleted, or backed up together.** If you delete one but not the other, cache lookups will return wrong results.

### 3. Streaming bypasses cache AND compression

When `stream=True`, the request goes straight to the proxy — no cache lookup, no cache store, no compression. This is by design (streaming responses can't be easily cached). If you're testing caching, use `stream=False`.

### 4. Embedder uses deferred import

`app/embedder.py` imports `sentence-transformers` inside `__init__()`, not at module level. This means tests can import the module without having the heavy ML library installed. Don't move the import to the top of the file.

### 5. Router defaults to COMPLEX when ambiguous

If the router can't confidently classify a prompt (mid-length, no keyword matches), it returns `COMPLEX`. This is intentional — it's safer to use a better model than risk quality degradation.

### 6. Compression requires BOTH thresholds

Compression only triggers when the conversation exceeds `CONTEXT_COMPRESSION_THRESHOLD_TOKENS` (default: 2000) **AND** has more than `COMPRESSION_MIN_TURNS` (default: 6) turns. Both conditions must be true.

### 7. Compression failure never blocks a request

If compression fails for any reason (LLM error, timeout, etc.), the request silently falls back to using the uncompressed messages. Check the `compression_ratio` field in telemetry — a ratio of 1.0 means compression was skipped or failed.

### 8. Telemetry uses SQLite WAL mode

`app/telemetry.py` enables WAL (Write-Ahead Logging) for concurrent writes. This means the database file may have accompanying `-wal` and `-shm` files. Don't delete them while the server is running.

### 9. Telemetry cost estimates are approximate

Cost per token varies by model and changes over time. The `estimated_cost_usd` field uses hardcoded rates in `app/costs.py` — these are documented as estimates, not exact billing.

### 10. `X-ContextForge-No-Compress` header skips compression

Set `X-ContextForge-No-Compress: true` on any request to bypass compression entirely. Useful for debugging or when you want exact message control.

---

## Before Starting Phase 6

1. **Clone and verify:**
   ```bash
   git clone https://github.com/aayush-1o/contextforge.git
   cd contextforge
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   pytest tests/ -v   # should be 54/54
   ```

2. **Create your branch:**
   ```bash
   git checkout -b phase/6-adaptive-thresholds
   ```

3. **Set up `.env`:**
   ```bash
   cp .env.example .env
   # Add your OPENAI_API_KEY
   ```

---

## Roadmap: Phases 6–9

| Phase | Feature | One-Line Description |
|-------|---------|---------------------|
| **6** | Adaptive Thresholds | Auto-tune cache similarity threshold based on hit rates; add `DELETE /v1/cache` invalidation endpoint. |
| **7** | Benchmarking Harness | End-to-end benchmark suite: cache hit rates, routing accuracy, latency p50/p95/p99, cost savings. |
| **8** | Dockerization | Production-ready Docker images with health checks, volume management, and optional GPU support. |
| **9** | Final Handoff | Complete API docs, deployment guide, architecture diagrams, and contributor onboarding. |

---

## File Map for Quick Orientation

| File | What It Does | You'll Touch It When... |
|------|-------------|------------------------|
| `app/main.py` | FastAPI app + lifespan + endpoint | Adding new middleware or pipeline steps |
| `app/proxy.py` | Sends requests to OpenAI/Anthropic | Adding Anthropic adapter or changing SDK usage |
| `app/cache.py` | Orchestrates FAISS + Redis lookups | Changing cache behavior or adding invalidation |
| `app/router.py` | Classifies prompts, picks models | Adding new classification rules or ML classifier |
| `app/compressor.py` | Summarizes older turns to reduce tokens | Adjusting compression strategy or thresholds |
| `app/telemetry.py` | SQLite telemetry writer/reader | Adding new metrics or changing aggregation |
| `app/costs.py` | Per-model cost estimation | Adding new model pricing or updating rates |
| `app/middleware.py` | Request wrapping middleware | Adding new request-level state or timing |
| `app/config.py` | Loads `.env` into typed Python config | Adding new environment variables |
| `app/models.py` | Pydantic schemas for API | Changing request/response format |
| `tests/conftest.py` | Shared test fixtures | Adding new mock services |
| `config/routing_rules.yaml` | Keyword lists, token thresholds | Tuning routing behavior |

---

## Test Coverage Summary

| File | Tests | What's Tested |
|------|-------|---------------|
| `test_proxy.py` | 12 | Health check, completions (5 scenarios), streaming (2), error propagation (4) |
| `test_cache.py` | 14 | VectorStore CRUD (6), SemanticCache hit/miss (5), endpoint integration (3) |
| `test_router.py` | 18 | Classifier unit (10), 1000-prompt accuracy (3), dataset validation (2), endpoint (3) |
| `test_compressor.py` | 5 | Token counting, min turns check, compression reduces messages, error fallback, system msg preservation |
| `test_telemetry.py` | 5 | Write/read roundtrip, cache hit rate summary, cost estimation, duplicate ID handling, total requests |
| **Total** | **54** | All pass without live API calls or running services |
