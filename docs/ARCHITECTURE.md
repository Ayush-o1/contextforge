# ContextForge Architecture

> Last updated: v0.7.0 (Phases 0–7 complete)

---

## System Overview

ContextForge is a proxy middleware that sits between LLM-powered apps and upstream providers (OpenAI, Anthropic). It exposes an OpenAI-compatible `POST /v1/chat/completions` endpoint so apps can connect with zero code changes. Behind the scenes, it applies optimizations to reduce cost and latency.

---

## What Is Built vs What Is Pending

| Component | Status | Phase |
|-----------|--------|-------|
| FastAPI Gateway | ✅ Built | 1 |
| OpenAI Proxy (passthrough) | ✅ Built | 1 |
| Pydantic Request/Response Models | ✅ Built | 1 |
| Streaming SSE Support | ✅ Built | 1 |
| Error Propagation (4xx/5xx) | ✅ Built | 1 |
| Embedding Service (all-MiniLM-L6-v2) | ✅ Built | 2 |
| FAISS Vector Index (Flat IP) | ✅ Built | 2 |
| Semantic Cache (FAISS + Redis) | ✅ Built | 2 |
| Redis TTL for Cache Entries | ✅ Built | 2 |
| FAISS/Redis Sync (read-through check) | ✅ Built | 2 |
| Rule-Based Complexity Classifier | ✅ Built | 3 |
| Model Tier Routing (OpenAI + Anthropic) | ✅ Built | 3 |
| Override Header (X-ContextForge-Model-Override) | ✅ Built | 3 |
| Context Compressor | ✅ Built | 4 |
| Telemetry (SQLite with WAL mode) | ✅ Built | 5 |
| Request Middleware | ✅ Built | 5 |
| Cost Estimation (per-model rates) | ✅ Built | 5 |
| Adaptive Similarity Thresholds | ✅ Built | 6 |
| Cache Invalidation API | ✅ Built | 6 |
| Cache Stats Endpoint | ✅ Built | 6 |
| 1000-Prompt Benchmark Dataset | ✅ Built | 7 |
| E2E Benchmark Runner | ✅ Built | 7 |
| Benchmark Utilities (paraphrase, latency stats) | ✅ Built | 7 |
| Production Docker | ⏳ Pending | 8 |
| Final Documentation & Handoff | ⏳ Pending | 9 |

---

## Request Pipeline (Current)

This is the actual request flow as of v0.7.0:

```
  Client Request (POST /v1/chat/completions)
       │
       ▼
  ┌─────────────────┐
  │  Validate JSON   │  Pydantic models (app/models.py)
  └────────┬────────┘
           │
           ▼
  ┌─────────────────┐
  │  Router Classify │  Token count + keyword signals (app/router.py)
  │  Select Model    │  SIMPLE → gpt-3.5-turbo, COMPLEX → gpt-4o
  └────────┬────────┘
           │
           ▼
  ┌─────────────────┐
  │  Compressor      │  If tokens > threshold AND turns > min_turns:
  │  (non-streaming)  │  summarize older turns via LLM (app/compressor.py)
  │                  │  Skip if X-ContextForge-No-Compress: true
  └────────┬────────┘
           │
           ▼
  ┌─────────────────┐
  │  Cache Lookup    │  Embed prompt → search FAISS → check Redis
  │  (non-streaming) │  Uses adaptive threshold (auto-tuned from telemetry)
  │                  │  If stream=True, cache + compression SKIPPED
  └────────┬────────┘
           │
      ┌────┴────┐
      │         │
   HIT ↓      MISS ↓
      │         │
      │    ┌────────────┐
      │    │ Proxy Call  │  Forward to OpenAI/Anthropic with routed model
      │    └────┬───────┘
      │         │
      │    ┌────────────┐
      │    │ Cache Store │  Save response in Redis + embed in FAISS
      │    └────┬───────┘
      │         │
      └────┬────┘
           │
           ▼
  ┌─────────────────┐
  │ Telemetry Write │  Log model, latency, cost, cache hit, compression
  │                 │  (app/telemetry.py → SQLite with WAL mode)
  └────────┬────────┘
           │
           ▼
  ┌─────────────────┐
  │  Return Response │  + X-Model-Tier, X-Model-Selected, X-Cache,
  │                 │    X-Compressed, X-Compression-Ratio headers
  └─────────────────┘
```

**Pipeline order (non-streaming):** Request → Validate → Router → Compressor → Cache Lookup → Proxy Forward → Cache Store → Telemetry Write → Response.

**Streaming requests** bypass compression and caching entirely — they go straight from Router to Proxy.

---

## Component Diagram

```
┌──────────────────┐     ┌────────────────────┐
│   Client / SDK   │────▶│  FastAPI Gateway    │
└──────────────────┘     │  (app/main.py)      │
                         └──────┬─────────────┘
                                │
              ┌─────────────────┼──────────────────┐
              │                 │                   │
              ▼                 ▼                   ▼
    ┌──────────────┐  ┌──────────────┐   ┌──────────────────┐
    │ Model Router │  │ Semantic     │   │ Proxy Client     │
    │ (router.py)  │  │ Cache        │   │ (proxy.py)       │
    │              │  │ (cache.py)   │   │                  │
    │ tiktoken +   │  │              │   │ openai-python    │
    │ keywords     │  │ Embedder +   │   │ SDK              │
    └──────────────┘  │ VectorStore  │   └────────┬─────────┘
                      └──────┬───────┘            │
                             │                    ▼
                      ┌──────┴───────┐   ┌──────────────────┐
                      │ FAISS Index  │   │ OpenAI / Anthropic│
                      │ Redis Cache  │   │ API               │
                      └──────────────┘   └──────────────────┘

    ┌──────────────┐   ┌──────────────────┐   ┌────────────────┐
    │ Adaptive     │   │ Context          │   │ Telemetry      │
    │ Threshold    │   │ Compressor       │   │ Writer         │
    │ Manager      │   │ (compressor.py)  │   │ (telemetry.py) │
    │ (adaptive.py)│   │                  │   │ SQLite + WAL   │
    └──────────────┘   └──────────────────┘   └────────────────┘

    ┌──────────────────┐
    │ Benchmark Runner │
    │ (benchmarks/     │
    │  run.py)         │
    └──────────────────┘
```

---

## Layer Responsibilities

| # | Layer | Responsibility | Files |
|---|-------|---------------|-------|
| 1 | API Gateway | Receives and validates OpenAI-compatible requests | `app/main.py`, `app/models.py` |
| 2 | Model Router | Classifies prompt complexity, selects model tier | `app/router.py`, `config/routing_rules.yaml` |
| 3 | Semantic Cache | Embeds prompts, searches FAISS, manages Redis cache | `app/cache.py`, `app/embedder.py`, `app/vector_store.py` |
| 4 | Context Compressor | Summarizes long conversation histories to reduce token count | `app/compressor.py` |
| 5 | Proxy Layer | Forwards requests to upstream LLM providers | `app/proxy.py` |
| 6 | Telemetry Layer | Tracks per-request metrics in SQLite (WAL mode) | `app/telemetry.py`, `app/costs.py` |
| 7 | Request Middleware | Wraps requests with telemetry state | `app/middleware.py` |
| 8 | Adaptive Threshold Manager | Auto-tunes similarity threshold from cache hit rates | `app/adaptive.py` |
| 9 | Cache Invalidation | Flush/invalidate cache entries, stats endpoint | `app/cache.py` (methods), `app/main.py` (endpoints) |
| 10 | Benchmark Suite | E2E benchmarks for routing accuracy, cache hit rates, latency | `benchmarks/run.py`, `benchmarks/benchmark_utils.py` |
| 11 | Config | Loads environment variables, validates at startup | `app/config.py` |

---

## Architecture Decision Records

All ADRs are documented in [DECISIONS.md](../DECISIONS.md). Summary:

| ADR | Decision | Status |
|-----|----------|--------|
| ADR-001 | FAISS over Qdrant for MVP | ✅ Implemented (Phase 2) |
| ADR-002 | Rule-based classifier first | ✅ Implemented (Phase 3) |
| ADR-003 | SQLite for telemetry | ✅ Implemented (Phase 5) |
| ADR-004 | all-MiniLM-L6-v2 embeddings | ✅ Implemented (Phase 2) |

---

## Telemetry Schema (Phase 5)

This schema is implemented in `app/telemetry.py` using SQLite with WAL mode for concurrent writes:

```sql
CREATE TABLE telemetry (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id          TEXT UNIQUE,
    timestamp           DATETIME,
    model_requested     TEXT,
    model_used          TEXT,
    cache_hit           BOOLEAN,
    similarity_score    REAL,
    prompt_tokens       INTEGER,
    completion_tokens   INTEGER,
    estimated_cost_usd  REAL,
    latency_ms          REAL,
    compressed          BOOLEAN,
    compression_ratio   REAL
);
```

**Endpoints:**
- `GET /v1/telemetry?limit=50&offset=0` — paginated records, newest first
- `GET /v1/telemetry/summary` — aggregated stats (total requests, cache hit rate, avg latency, total cost, p95 latency)

---

## Adaptive Threshold Schema (Phase 6)

```sql
CREATE TABLE threshold_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT,
    threshold       REAL,
    cache_hit_rate  REAL,
    action          TEXT  -- 'raised', 'lowered', or 'unchanged'
);
```

**Endpoints:**
- `GET /v1/threshold` — current threshold, baseline, last evaluation
- `POST /v1/threshold/evaluate` — manually trigger threshold evaluation
- `GET /v1/cache/stats` — vector count, Redis keys, active threshold
- `DELETE /v1/cache` — flush FAISS + Redis
- `DELETE /v1/cache/{key}` — invalidate a specific entry

---

## Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------| 
| Web Framework | FastAPI | 0.115.6 |
| Embedding Model | all-MiniLM-L6-v2 | via sentence-transformers 3.3.1 |
| Vector Index | FAISS (CPU) | 1.9.0.post1 |
| Cache Store | Redis | 7 (Alpine) |
| Token Counter | tiktoken | 0.8.0 |
| LLM SDKs | openai-python / anthropic-python | 1.59.7 / 0.42.0 |
| Config | Pydantic Settings | 2.7.1 |
| Logging | structlog | 24.4.0 |
| Testing | pytest + httpx | 8.3.4 / 0.28.1 |
| Containerization | Docker + Docker Compose | — |
