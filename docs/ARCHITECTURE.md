# ContextForge Architecture

> Last updated: v0.5.0 (Phases 0–5 complete)

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
| Adaptive Thresholds | ⏳ Not started | 6 |
| Cache Invalidation API | ⏳ Not started | 6 |

---

## Request Pipeline (Current)

This is the actual request flow as of v0.5.0:

```
  Client Request
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
  └────────┬────────┘
           │
           ▼
  ┌─────────────────┐
  │  Cache Lookup    │  Embed prompt → search FAISS → check Redis
  │  (non-streaming) │  If stream=True, cache + compression SKIPPED
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
  │ Telemetry Write │  Log model, latency, cost, cache hit (app/telemetry.py)
  └────────┬────────┘
           │
           ▼
  ┌─────────────────┐
  │  Return Response │  + X-Model-Tier, X-Model-Selected, X-Cache-Hit,
  │                 │    X-Compressed, X-Compression-Ratio headers
  └─────────────────┘
```

> **Note:** Adaptive Thresholds (Phase 6) will add auto-tuning of the cache similarity threshold and a `DELETE /v1/cache` endpoint for cache invalidation.

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
```

---

## Layer Responsibilities

| # | Layer | Responsibility | Files |
|---|-------|---------------|-------|
| 1 | API Gateway | Receives and validates OpenAI-compatible requests | `app/main.py`, `app/models.py` |
| 2 | Model Router | Classifies prompt complexity, selects model tier | `app/router.py`, `config/routing_rules.yaml` |
| 3 | Semantic Cache | Embeds prompts, searches FAISS, manages Redis cache | `app/cache.py`, `app/embedder.py`, `app/vector_store.py` |
| 4 | Proxy Layer | Forwards requests to upstream LLM providers | `app/proxy.py` |
| 5 | Config | Loads environment variables, validates at startup | `app/config.py` |
| 6 | Context Compressor | Summarizes long conversation histories to reduce token count | `app/compressor.py` |
| 7 | Cost Estimator | Calculates per-model cost estimates | `app/costs.py` |
| 8 | Telemetry Layer | Tracks per-request metrics in SQLite (WAL mode) | `app/telemetry.py` |
| 9 | Request Middleware | Wraps requests with telemetry state | `app/middleware.py` |

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
