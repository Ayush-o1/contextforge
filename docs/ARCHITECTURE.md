# ContextForge Architecture
> Last updated: v1.0.0 (Phases 0–9 complete, production release)

---

## Overview

ContextForge is a proxy middleware that sits between LLM-powered applications and upstream providers (OpenAI, Anthropic). It exposes an OpenAI-compatible `POST /v1/chat/completions` endpoint so apps can connect with zero code changes. Behind the scenes, it applies three optimizations to reduce cost and latency:

1. **Context compression** — summarizes long conversation histories to reduce token usage
2. **Semantic caching** — returns cached responses for semantically similar prompts
3. **Smart model routing** — routes simple prompts to cheaper models automatically

---

## Build Status

| Component | Status | Phase |
|-----------|:------:|:-----:|
| FastAPI Gateway | ✅ | 1 |
| OpenAI Proxy (passthrough + streaming) | ✅ | 1 |
| Pydantic Request/Response Models | ✅ | 1 |
| Error Propagation (4xx/5xx) | ✅ | 1 |
| Embedding Service (all-MiniLM-L6-v2) | ✅ | 2 |
| FAISS Vector Index | ✅ | 2 |
| Semantic Cache (FAISS + Redis) | ✅ | 2 |
| Rule-Based Complexity Classifier | ✅ | 3 |
| Model Tier Routing | ✅ | 3 |
| Context Compressor | ✅ | 4 |
| Telemetry (SQLite, WAL mode) | ✅ | 5 |
| Cost Estimation | ✅ | 5 |
| Adaptive Similarity Thresholds | ✅ | 6 |
| Cache Invalidation API | ✅ | 6 |
| 1000-Prompt Benchmark Suite | ✅ | 7 |
| E2E Benchmark Runner | ✅ | 7 |
| Docker Compose | ✅ | 8 |
| Modular Dashboard | ✅ | 8 |
| Production Documentation | ✅ | 9 |
| E2E Integration Tests (22 tests) | ✅ | 10 |
| Multi-Stage Dockerfile + Docker Hardening | ✅ | 10 |
| Railway Deployment Pipeline | ✅ | 10 |
| TelemetryMiddleware Registration | ✅ | 10 |
| Dashboard Static Mount (`/dashboard`) | ✅ | 10 |

---

## Request Pipeline


This is the actual request flow as of v1.0.0:

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
│  (non-streaming) │  Summarize older turns via LLM (app/compressor.py)
│                  │  Skip if X-ContextForge-No-Compress: true
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Cache Lookup    │  Embed prompt → search FAISS → check Redis
│  (non-streaming) │  Uses adaptive threshold (auto-tuned from telemetry)
│                  │  If stream=True → cache + compression SKIPPED
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
 HIT ↓      MISS ↓
    │         │
    │    ┌────────────┐
    │    │ Proxy Call  │  Forward to upstream with routed model
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
│                 │  (app/telemetry.py → SQLite WAL mode)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Return Response │  + X-Cache-Hit, X-Model-Tier, X-Model-Selected,
│                  │    X-Compressed, X-Compression-Ratio headers
└──────────────────┘
```

**Non-streaming:** Request → Validate → Router → Compressor → Cache Lookup → Proxy → Cache Store → Telemetry → Response

**Streaming:** Request → Validate → Router → Proxy (bypasses compression and caching entirely)

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

    ┌──────────────────┐   ┌───────────────────────┐
    │ Benchmark Runner │   │ Dashboard              │
    │ (benchmarks/)    │   │ (docs/dashboard/)      │
    └──────────────────┘   │ Static HTML/JS/CSS     │
                           │ → fetches /v1/telemetry│
                           └───────────────────────┘
```

---

## Layer Responsibilities

| # | Layer | Responsibility | Files |
|---|-------|---------------|-------|
| 1 | API Gateway | Receives and validates OpenAI-compatible requests | `app/main.py`, `app/models.py` |
| 2 | Model Router | Classifies prompt complexity, selects model tier | `app/router.py`, `config/routing_rules.yaml` |
| 3 | Context Compressor | Summarizes long conversations to reduce token count | `app/compressor.py` |
| 4 | Semantic Cache | Embeds prompts, searches FAISS, manages Redis cache | `app/cache.py`, `app/embedder.py`, `app/vector_store.py` |
| 5 | Proxy Layer | Forwards requests to upstream LLM providers | `app/proxy.py` |
| 6 | Telemetry | Tracks per-request metrics in SQLite (WAL mode) | `app/telemetry.py`, `app/costs.py` |
| 7 | Middleware | Wraps requests with telemetry state | `app/middleware.py` |
| 8 | Adaptive Thresholds | Auto-tunes similarity threshold from cache hit rates | `app/adaptive.py` |
| 9 | Cache Management | Flush/invalidate cache entries, stats | `app/cache.py`, `app/main.py` |
| 10 | Dashboard | Real-time telemetry visualization | `docs/dashboard/` |
| 11 | Benchmarks | E2E tests for routing, caching, and latency | `benchmarks/` |
| 12 | Config | Loads and validates environment variables at startup | `app/config.py` |

---

## Dashboard Architecture

The dashboard is a standalone static web app at `docs/dashboard/`. It connects to the backend API for live data and falls back to mock data when the backend is unavailable.

```
docs/dashboard/
├── index.html          # Page shell with all sections
├── css/style.css       # Design system (dark theme)
└── js/
    ├── data.js         # Mock data + connection check
    ├── ui.js           # Toast, modal, sidebar, formatters
    ├── charts.js       # 6 Chart.js charts
    ├── tables.js       # Table rendering + pagination
    └── app.js          # Navigation, data loading, normalization
```

**API endpoints used by dashboard:**
- `GET /health` — connection detection
- `GET /v1/telemetry?limit=50` — request records
- `GET /v1/telemetry/summary` — aggregated metrics
- `GET /v1/cache/stats` — cache statistics

For full details, see [DASHBOARD.md](DASHBOARD.md).

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
| Dashboard | Chart.js 4.x | CDN |
| Containerization | Docker + Docker Compose | — |

---

## Telemetry Schema

Implemented in `app/telemetry.py` using SQLite with WAL mode for concurrent writes:

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

## Adaptive Threshold Schema

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

## Architecture Decision Records

All ADRs are documented in [DECISIONS.md](../DECISIONS.md).

| ADR | Decision | Status |
|-----|----------|--------|
| ADR-001 | FAISS over Qdrant for MVP | ✅ Implemented (Phase 2) |
| ADR-002 | Rule-based classifier first | ✅ Implemented (Phase 3) |
| ADR-003 | SQLite for telemetry | ✅ Implemented (Phase 5) |
| ADR-004 | all-MiniLM-L6-v2 embeddings | ✅ Implemented (Phase 2) |

Each ADR includes context, decision rationale, and a documented upgrade path.

