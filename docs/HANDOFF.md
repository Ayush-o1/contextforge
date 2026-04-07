# ContextForge — Developer Handoff

> Onboarding guide for developers picking up this project.

---

## Project State

| Item | Value |
|------|-------|
| **Last completed phase** | Phase 5 (Universal Tool-Use & Final Handoff) |
| **Version** | `v1.0.0` |
| **Tests** | 132+ unit + integration tests passing |
| **Lint** | ruff clean (zero errors) |
| **Router accuracy** | 92.8% on 1000-prompt labeled dataset |
| **Branch** | `main` — all phases merged |
| **Tags** | `v0.1.0` through `v1.0.0` (one per phase) |

---

## Getting Started

```bash
# 1. Clone the repository
git clone https://github.com/Ayush-o1/contextforge.git
cd contextforge

# 2. Set up Python environment
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3. Verify everything works
PYTHONPATH=. pytest tests/ -v   # should be 84/84

# 4. Configure environment
cp .env.example .env
# Add your OPENAI_API_KEY

# 5. Start Redis
docker run -d -p 6379:6379 redis:7-alpine

# 6. Run the server
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## What Works Right Now

1. **`POST /v1/chat/completions`** — Full OpenAI-compatible endpoint
2. **Semantic caching** — FAISS + Redis, cosine similarity with adaptive threshold (default 0.92)
3. **Model routing** — Rule-based classifier: simple → gpt-3.5-turbo, complex → gpt-4o (92.8% accuracy)
4. **Context compression** — Long conversations automatically summarized to reduce token usage
5. **Telemetry** — Per-request metrics logged to SQLite (model, latency, cost, cache hit, compression)
6. **Adaptive thresholds** — Auto-tune cache similarity threshold based on hit rates
7. **Cache invalidation** — `DELETE /v1/cache`, `DELETE /v1/cache/{key}`, `GET /v1/cache/stats`
8. **Streaming** — SSE passthrough (bypasses cache and compression by design)
9. **Error propagation** — Upstream 4xx/5xx errors surface correctly
10. **Benchmark suite** — 1000-prompt dataset, E2E benchmark runner with `--dry-run` for CI
11. **Dashboard** — Built-in HTML dashboard at `GET /dashboard`
12. **Health check** — `GET /health` returns `{"status":"ok","version":"1.0.0"}`
13. **Telemetry API** — `GET /v1/telemetry` (paginated) + `GET /v1/telemetry/summary` (aggregated)
14. **Threshold API** — `GET /v1/threshold` + `POST /v1/threshold/evaluate`

---

## File Map

Use this to quickly orient yourself in the codebase.

### Core Application (`app/`)

| File | What It Does | When You'll Touch It |
|------|-------------|----------------------|
| `main.py` | FastAPI app, lifespan, all endpoints | Adding new endpoints or pipeline steps |
| `proxy.py` | Sends requests to OpenAI/Anthropic | Changing SDK usage or adding providers |
| `cache.py` | Orchestrates FAISS + Redis lookups | Changing cache behavior or invalidation |
| `router.py` | Classifies prompts, picks models | Adding classification rules or ML classifier |
| `compressor.py` | Summarizes older turns | Adjusting compression strategy |
| `telemetry.py` | SQLite telemetry writer/reader | Adding new metrics or aggregations |
| `adaptive.py` | Adaptive threshold tuning | Changing threshold strategy |
| `costs.py` | Per-model cost estimation | Adding new model pricing |
| `middleware.py` | Request wrapping middleware | Adding request-level state |
| `config.py` | Loads `.env` into typed config | Adding new environment variables |
| `models.py` | Pydantic schemas for the API | Changing request/response format |
| `embedder.py` | Sentence-transformer wrapper | Changing embedding model |
| `vector_store.py` | FAISS index management | Changing vector storage |

### Configuration

| File | What It Does |
|------|-------------|
| `config/routing_rules.yaml` | Keyword lists, token thresholds, model mappings |
| `.env.example` | Template for all environment variables |

### Tests & Benchmarks

| File | What It Does |
|------|-------------|
| `tests/conftest.py` | Shared test fixtures (mock Redis, FAISS, proxy) |
| `tests/test_*.py` | Test files (84 tests total) |
| `benchmarks/run_benchmark.py` | E2E benchmark runner |
| `benchmarks/benchmark_utils.py` | Paraphrase, latency stats, accuracy utils |
| `benchmarks/prompts_labeled.json` | 1000 labeled prompts for testing |

### Infrastructure

| File | What It Does |
|------|-------------|
| `Dockerfile` | Python 3.11 container image |
| `docker-compose.yml` | App + Redis service orchestration |
| `.github/workflows/ci.yml` | GitHub Actions: lint + test + benchmark |

---

## Known Gotchas

### 1. `get_settings()` uses `@lru_cache`

Settings are loaded once from `.env` and cached for the process lifetime. Changes at runtime won't take effect until restart. In tests, force reload with:

```python
from app.config import get_settings
get_settings.cache_clear()
```

### 2. FAISS index has a companion file

The FAISS index and its ID map are two separate files:
- `data/faiss.index` — the vector index
- `data/faiss.index.idmap` — JSON mapping of index positions to cache keys

**Both files must be moved, deleted, or backed up together.** If one is missing, cache lookups will return wrong results.

### 3. Streaming bypasses cache and compression

When `stream=True`, the request goes straight to the proxy — no cache lookup, no cache store, no compression. This is by design (streaming responses can't be easily cached).

### 4. Embedder uses deferred import

`app/embedder.py` imports `sentence-transformers` inside `__init__()`, not at module level. This allows tests to import the module without the heavy ML library. Don't move the import to the top of the file.

### 5. Router defaults to COMPLEX when ambiguous

If the router can't confidently classify a prompt, it returns `COMPLEX`. This is intentional — it's safer to use a better model than risk quality issues.

### 6. Compression requires both thresholds

Compression only triggers when the conversation exceeds `CONTEXT_COMPRESSION_THRESHOLD_TOKENS` (default: 2000) **AND** has more than `COMPRESSION_MIN_TURNS` (default: 6) turns. Both conditions must be true.

### 7. Compression failure never blocks a request

If compression fails (LLM error, timeout, etc.), the request silently falls back to uncompressed messages. Check `compression_ratio` in telemetry — a value of `1.0` means compression was skipped or failed.

### 8. Telemetry uses SQLite WAL mode

`app/telemetry.py` enables WAL (Write-Ahead Logging) for concurrent writes. The database file may have accompanying `-wal` and `-shm` files. Don't delete them while the server is running.

### 9. Cost estimates are approximate

The `estimated_cost_usd` field uses hardcoded per-token rates in `app/costs.py`. These are estimates — actual billing from OpenAI may differ slightly.

### 10. `X-ContextForge-No-Compress` header

Set `X-ContextForge-No-Compress: true` on any request to bypass compression entirely. Useful for debugging or when you need exact message control.

### 11. Adaptive threshold has min/max caps

The threshold self-tunes between `ADAPTIVE_THRESHOLD_MIN` (0.70) and `ADAPTIVE_THRESHOLD_MAX` (0.98). Step size is ±0.01 per evaluation. Hit rate thresholds: >60% → raise, <20% → lower.

### 12. Cache endpoints handle Redis unavailability

`GET /v1/cache/stats` and `DELETE /v1/cache` return partial results (vector count but 0 Redis keys) if Redis is not running. Errors are logged but don't crash the endpoint.

### 13. `datetime.utcnow()` deprecation

`app/adaptive.py` uses `datetime.datetime.utcnow()` which shows a DeprecationWarning on Python 3.12+. Can be fixed by switching to `datetime.datetime.now(datetime.UTC)`.

### 14. Dashboard is a static site

The dashboard lives at `docs/dashboard/index.html`. It is a standalone static web app — no server-side rendering, no build step. It connects to `http://localhost:8000` for live data and falls back to mock data when the backend is unavailable. See [docs/DASHBOARD.md](DASHBOARD.md) for the full architecture.

### 15. Telemetry is local-only

All telemetry is stored locally in SQLite at `./data/telemetry.db`. No request data is sent to any external service.

---

## Test Coverage

| File | Tests | What's Tested |
|------|:-----:|---------------|
| `test_proxy.py` | 12 | Health check, completions, streaming, error propagation |
| `test_cache.py` | 14 | VectorStore CRUD, SemanticCache hit/miss, endpoint integration |
| `test_router.py` | 18 | Classifier unit tests, 1000-prompt accuracy, dataset validation |
| `test_compressor.py` | 5 | Token counting, min turns, compression, error fallback, system messages |
| `test_telemetry.py` | 5 | Write/read roundtrip, summary, cost estimation, dedup, total requests |
| `test_adaptive.py` | 8 | Threshold raise/lower/unchanged, min/max caps, DB write, endpoints |
| `test_cache_invalidation.py` | 7 | Flush, invalidate, stats, idempotent flush, endpoint schemas |
| `test_benchmarks.py` | 15 | Paraphrase, latency stats, routing accuracy, confusion matrix |
| **Total** | **84** | All pass without live API calls or running services |

---

## How to Add a New LLM Provider

Since ContextForge uses **LiteLLM** as its universal provider layer, adding support for any new provider takes less than 5 minutes and requires **zero code changes**.

### Step 1 — Get the API key

Sign up at the provider's developer portal and obtain an API key.

### Step 2 — Add the key to `.env`

```bash
# Example: TogetherAI
TOGETHER_API_KEY=your-key-here
```

LiteLLM reads provider keys directly from environment variables using the naming convention `{PROVIDER}_API_KEY`.

### Step 3 — Use the provider-prefixed model name

```python
# In your request:
{"model": "together_ai/mistralai/Mixtral-8x7B-Instruct-v0.1", ...}
```

LiteLLM's prefix routing automatically sends the request to the correct provider.

### Step 4 (optional) — Register in the Router for failover

Add the provider to `ProxyClient._build_model_list()` in `app/proxy.py`:

```python
if settings.together_api_key:
    add("simple-tier", "together_ai/mistralai/Mixtral-8x7B-Instruct-v0.1", settings.together_api_key)
```

And add the corresponding config field in `app/config.py`:

```python
together_api_key: str = ""
```

### Step 5 (optional) — Update the translation guard

If the new provider does **not** support function/tool calling, add its prefix to `_TOOL_UNSUPPORTED_PROVIDERS` in `app/proxy.py`:

```python
_TOOL_UNSUPPORTED_PROVIDERS: frozenset[str] = frozenset({
    "ollama",
    "ollama_chat",
    "huggingface",
    "replicate",
    "your_new_provider",   # ← add here if no tool support
})
```

### Supported Providers (LiteLLM handles all translation)

| Provider | Prefix | Tool Support | Notes |
|----------|--------|:---:|-------|
| OpenAI | `openai/` | ✅ | Full function calling |
| Anthropic | `anthropic/` | ✅ | Native tool use format |
| Google Gemini | `gemini/` | ✅ | functionDeclarations format |
| Groq | `groq/` | ✅ (llama3-70b+) | Not all models |
| Mistral | `mistral/` | ✅ | |
| Cohere | `cohere/` | ✅ | |
| xAI (Grok) | `xai/` | ✅ | |
| Ollama | `ollama/` | ❌ | Local only, no tools |
| Together AI | `together_ai/` | ✅ | |
| Bedrock | `bedrock/` | ✅ | |

---

## What's Next

All 5 phases are complete. Potential future enhancements:

- ML-based complexity classifier (replacing rule-based router)
- Qdrant migration for vector storage at scale
- Dashboard deployment as a hosted page
- Streaming tool-call support

## Related Documentation

| Document | Description |
|----------|-------------|
| [SETUP.md](SETUP.md) | Local development setup |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System design and component diagram |
| [API.md](API.md) | Full API reference |
| [DASHBOARD.md](DASHBOARD.md) | Dashboard architecture and guide |
| [CONFIGURATION.md](CONFIGURATION.md) | Environment variable reference |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Common issues and fixes |

