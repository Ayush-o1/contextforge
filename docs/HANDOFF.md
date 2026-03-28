# ContextForge — Developer Handoff

> For the next developer picking up from Phase 8 onwards.

---

## Project State

| Item | Value |
|------|-------|
| **Last completed phase** | Phase 7 (Testing & Benchmarking Harness) |
| **Version** | `v0.7.0` |
| **Tests** | 84/84 passing |
| **Lint** | ruff clean (zero errors) |
| **Router accuracy** | 92.8% on 1000-prompt labeled dataset |
| **Branch** | `main` has all phases merged |
| **Tags** | `v0.1.0`–`v0.7.0` (one per phase) |

---

## What Works Right Now

1. **`POST /v1/chat/completions`** — Full OpenAI-compatible endpoint
2. **Semantic caching** — FAISS + Redis, cosine similarity with adaptive threshold (default 0.92)
3. **Model routing** — Rule-based classifier routes simple→gpt-3.5-turbo, complex→gpt-4o (92.8% accuracy)
4. **Context compression** — Long conversations automatically summarized to reduce token usage
5. **Telemetry** — Per-request metrics logged to SQLite (model, latency, cost, cache hit, compression)
6. **Adaptive thresholds** — Auto-tune cache similarity threshold based on hit rates
7. **Cache invalidation** — `DELETE /v1/cache`, `DELETE /v1/cache/{key}`, `GET /v1/cache/stats`
8. **Streaming** — SSE passthrough works (bypasses cache and compression)
9. **Error propagation** — Upstream 4xx/5xx errors surface correctly to the caller
10. **Benchmark suite** — 1000-prompt dataset, E2E benchmark runner with `--dry-run` mode for CI
11. **Dashboard** — Built-in HTML dashboard at `GET /dashboard` visualizes telemetry data
12. **`GET /health`** — Returns `{"status":"ok","version":"0.7.0"}`
13. **`GET /v1/telemetry`** — Paginated telemetry records (stored locally in `./data/telemetry.db`)
14. **`GET /v1/telemetry/summary`** — Aggregated stats (cache hit rate, avg latency, total cost)
15. **`GET /v1/threshold`** — Current adaptive threshold info
16. **`POST /v1/threshold/evaluate`** — Manually trigger threshold evaluation

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

### 11. Adaptive threshold has min/max caps

The adaptive threshold self-tunes between `ADAPTIVE_THRESHOLD_MIN` (0.70) and `ADAPTIVE_THRESHOLD_MAX` (0.98). The step size is ±0.01 per evaluation. The hit rate thresholds are: >60% → raise, <20% → lower.

### 12. Cache stats/flush gracefully handle Redis unavailability

`GET /v1/cache/stats` and `DELETE /v1/cache` will return partial results (vector count but 0 Redis keys) if Redis is not running. Errors are logged but don't crash the endpoint.

### 13. `datetime.utcnow()` deprecation warning

`app/adaptive.py` uses `datetime.datetime.utcnow()` which triggers a DeprecationWarning on Python 3.12+. This is cosmetic and can be fixed by switching to `datetime.datetime.now(datetime.UTC)`.

### 14. Dashboard is served via static file mount

`app/main.py` mounts the `docs/` directory as `/static` and serves the dashboard HTML at `GET /dashboard`. The dashboard runs entirely client-side with Chart.js and connects to the telemetry API endpoints. If opening `docs/dashboard.html` directly from the filesystem (file:// protocol), it runs in demo mode with mock data since it cannot reach the API.

### 15. Telemetry data is local-only

All telemetry is stored locally in SQLite at `./data/telemetry.db`. No request data is sent to any external service. The file uses WAL mode and can be safely queried with any SQLite client while the server is running.

---

## What Phase 8 Requires

Phase 8 is **Dockerization & Deployment**. Here's what needs to be done:

### Production Dockerfile
- Multi-stage build (builder → runtime) to minimize image size
- Non-root user for security
- `HEALTHCHECK` instruction pointing to `/health`
- Pin base image (e.g., `python:3.11-slim-bookworm`)

### docker-compose.yml Updates
- Health checks for both app and Redis services
- Volume mounts for SQLite persistence (`./data/telemetry.db`)
- Volume mounts for FAISS index persistence (`./data/faiss.index`, `./data/faiss.index.idmap`)
- Named volumes for Redis data persistence
- Restart policies (`unless-stopped`)
- Environment variable passthrough from `.env`

### Smoke Test
- `docker compose up --build -d` must succeed from a fresh clone
- `curl http://localhost:8000/health` must return `{"status":"ok","version":"0.7.0"}`
- The Quick Start section in README must work end-to-end

### Verification
- Build succeeds without errors
- Container starts and health check passes
- Data persists across container restarts (SQLite, FAISS)
- Redis connects properly between containers
- Dashboard loads at `http://localhost:8000/dashboard` (the route already exists in `app/main.py`)

---

## Before Starting Phase 8

1. **Clone and verify:**
   ```bash
   git clone https://github.com/aayush-1o/contextforge.git
   cd contextforge
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   PYTHONPATH=. pytest tests/ -v   # should be 84/84
   ```

2. **Create your branch:**
   ```bash
   git checkout -b phase/8-dockerization
   ```

3. **Set up `.env`:**
   ```bash
   cp .env.example .env
   # Add your OPENAI_API_KEY
   ```

---

## Roadmap: Phases 8–9

| Phase | Feature | One-Line Description |
|-------|---------|---------------------|
| **8** | Dockerization | Production-ready Docker images with health checks, volume management, and multi-stage builds. |
| **9** | Final Handoff | Complete API docs, deployment guide, architecture diagrams, and contributor onboarding. |

---

## File Map for Quick Orientation

| File | What It Does | You'll Touch It When... |
|------|-------------|------------------------|
| `app/main.py` | FastAPI app + lifespan + all endpoints | Adding new endpoints or pipeline steps |
| `app/proxy.py` | Sends requests to OpenAI/Anthropic | Adding Anthropic adapter or changing SDK usage |
| `app/cache.py` | Orchestrates FAISS + Redis lookups | Changing cache behavior or invalidation |
| `app/router.py` | Classifies prompts, picks models | Adding new classification rules or ML classifier |
| `app/compressor.py` | Summarizes older turns to reduce tokens | Adjusting compression strategy or thresholds |
| `app/telemetry.py` | SQLite telemetry writer/reader | Adding new metrics or changing aggregation |
| `app/adaptive.py` | Adaptive threshold auto-tuning | Changing threshold strategy or evaluation window |
| `app/costs.py` | Per-model cost estimation | Adding new model pricing or updating rates |
| `app/middleware.py` | Request wrapping middleware | Adding new request-level state or timing |
| `app/config.py` | Loads `.env` into typed Python config | Adding new environment variables |
| `app/models.py` | Pydantic schemas for API | Changing request/response format |
| `tests/conftest.py` | Shared test fixtures | Adding new mock services |
| `config/routing_rules.yaml` | Keyword lists, token thresholds | Tuning routing behavior |
| `benchmarks/run.py` | E2E benchmark runner | Adding new benchmark types |
| `benchmarks/benchmark_utils.py` | Paraphrase, latency stats, accuracy | Extending benchmark utilities |
| `Dockerfile` | Container image definition | Phase 8: multi-stage build, non-root user |
| `docker-compose.yml` | Service orchestration | Phase 8: health checks, volume mounts |

---

## Test Coverage Summary

| File | Tests | What's Tested |
|------|-------|---------------|
| `test_proxy.py` | 12 | Health check, completions (5 scenarios), streaming (2), error propagation (4) |
| `test_cache.py` | 14 | VectorStore CRUD (6), SemanticCache hit/miss (5), endpoint integration (3) |
| `test_router.py` | 18 | Classifier unit (10), 1000-prompt accuracy (3), dataset validation (2), endpoint (3) |
| `test_compressor.py` | 5 | Token counting, min turns check, compression reduces messages, error fallback, system msg preservation |
| `test_telemetry.py` | 5 | Write/read roundtrip, cache hit rate summary, cost estimation, duplicate ID handling, total requests |
| `test_adaptive.py` | 8 | Threshold raise/lower/unchanged, min/max caps, DB write, GET/POST endpoint schemas |
| `test_cache_invalidation.py` | 7 | VectorStore flush, cache invalidate/flush/stats, idempotent flush, endpoint schemas |
| `test_benchmarks.py` | 15 | Paraphrase, latency stats (p50/p95/p99), routing accuracy, confusion matrix, JSON serialization |
| **Total** | **84** | All pass without live API calls or running services |
