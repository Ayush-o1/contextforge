# ContextForge — Developer Handoff

> For the next developer picking up from Phase 4 onwards.

---

## Project State

| Item | Value |
|------|-------|
| **Last completed phase** | Phase 3 (Model Router) |
| **Version** | `v0.3.0` |
| **Tests** | 44/44 passing |
| **Lint** | ruff clean (zero errors) |
| **Branch** | `develop` has all phases merged |
| **Tags** | `v0.1.0` (Phase 1), `v0.2.0` (Phase 2), `v0.3.0` (Phase 3) |

---

## What Works Right Now

1. **`POST /v1/chat/completions`** — Full OpenAI-compatible endpoint
2. **Semantic caching** — FAISS + Redis, cosine similarity ≥0.92 threshold
3. **Model routing** — Rule-based classifier routes simple→gpt-3.5-turbo, complex→gpt-4o
4. **Streaming** — SSE passthrough works (but bypasses cache)
5. **Error propagation** — Upstream 4xx/5xx errors surface correctly to the caller
6. **`GET /health`** — Returns `{"status":"ok","version":"0.3.0"}`

---

## Known Gotchas

These are the five things that will bite you if you don't know about them:

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

### 3. Streaming bypasses cache

When `stream=True`, the request goes straight to the proxy — no cache lookup, no cache store. This is by design (streaming responses can't be easily cached). If you're testing caching, use `stream=False`.

### 4. Embedder uses deferred import

`app/embedder.py` imports `sentence-transformers` inside `__init__()`, not at module level. This means tests can import the module without having the heavy ML library installed. Don't move the import to the top of the file.

### 5. Router defaults to COMPLEX when ambiguous

If the router can't confidently classify a prompt (mid-length, no keyword matches), it returns `COMPLEX`. This is intentional — it's safer to use a better model than risk quality degradation.

---

## Before Starting Phase 4

1. **Clone and verify:**
   ```bash
   git clone https://github.com/aayush-1o/contextforge.git
   cd contextforge
   git checkout develop
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   pytest tests/ -v   # should be 44/44
   ```

2. **Create your branch:**
   ```bash
   git checkout -b phase/4-compressor
   ```

3. **Set up `.env`:**
   ```bash
   cp .env.example .env
   # Add your OPENAI_API_KEY
   ```

4. **Check the stubs:**
   - `app/compressor.py` — empty stub, this is where Phase 4 goes
   - `tests/test_compressor.py` — empty stub for your tests

---

## Roadmap: Phases 4–9

| Phase | Feature | One-Line Description |
|-------|---------|---------------------|
| **4** | Context Compressor | Summarize long conversation histories using the LLM itself to reduce token count before forwarding. |
| **5** | Telemetry Layer | Write per-request metrics (model, latency, cost, cache hit) to SQLite via SQLModel. |
| **6** | Adaptive Thresholds | Auto-tune cache similarity threshold based on hit rates; add cache invalidation API endpoints. |
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
| **Total** | **44** | All pass without live API calls or running services |
