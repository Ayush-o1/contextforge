# ContextForge Architecture

> Last updated: v0.3.0 (Phases 0–3 complete)

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
| Context Compressor | ⏳ Stub | 4 |
| Telemetry (SQLite) | ⏳ Stub | 5 |
| Request Middleware | ⏳ Stub | 5 |
| Adaptive Thresholds | ⏳ Not started | 6 |
| Cache Invalidation API | ⏳ Not started | 6 |

---

## Request Pipeline (Current)

This is the actual request flow as of v0.3.0:

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
  │  Cache Lookup    │  Embed prompt → search FAISS → check Redis
  │  (non-streaming) │  If stream=True, cache is SKIPPED
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
  │  Return Response │  + X-Model-Tier, X-Model-Selected, X-Cache-Hit headers
  └─────────────────┘
```

> **Note:** Context Compression (Phase 4) will be inserted between Validate and Router Classify. The `X-ContextForge-No-Compress` header will allow skipping it.

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
| 6 | *(Phase 4)* Compressor | Will compress long conversation histories | `app/compressor.py` (stub) |
| 7 | *(Phase 5)* Telemetry | Will track per-request metrics in SQLite | `app/telemetry.py` (stub) |

---

## Architecture Decision Records

All ADRs are documented in [DECISIONS.md](../DECISIONS.md). Summary:

| ADR | Decision | Status |
|-----|----------|--------|
| ADR-001 | FAISS over Qdrant for MVP | ✅ Implemented (Phase 2) |
| ADR-002 | Rule-based classifier first | ✅ Implemented (Phase 3) |
| ADR-003 | SQLite for telemetry | ⏳ Pending implementation (Phase 5) |
| ADR-004 | all-MiniLM-L6-v2 embeddings | ✅ Implemented (Phase 2) |

---

## Telemetry Schema (Phase 5)

This schema is designed but not yet implemented:

```sql
CREATE TABLE telemetry (
    id                  INTEGER PRIMARY KEY,
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
