# ContextForge — Sub-Phase Study Breakdown (Phases 1–3)

> **Internal document.** This is an architectural study guide used during development. It is preserved for historical reference and code comprehension. Not intended for external contributors — see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/HANDOFF.md](docs/HANDOFF.md) instead.

> Owner: Ayush | Generated for structured, study-friendly planning

---

## Phase 1 — API Gateway + OpenAI-Compatible Endpoint + SSE Streaming

### 1.1 — Configuration & Settings Bootstrap
| Field | Detail |
|---|---|
| **Files** | `app/config.py` |
| **Responsibility** | Loads all env vars via Pydantic `Settings`. Redis URL, API keys, feature flags, threshold bounds. |
| **Why separate** | Every other module depends on `get_settings()`. Study this first to understand what knobs exist. |
| **Difficulty** | 2/10 |
| **Depends on** | Nothing |

---

### 1.2 — Request & Response Models
| Field | Detail |
|---|---|
| **Files** | `app/models.py` |
| **Responsibility** | Pydantic schemas for `ChatCompletionRequest`, `HealthResponse`, and all message types. |
| **Why separate** | These models are imported everywhere. Fields like `stream`, `tools`, `messages` must be understood before reading any route. |
| **Difficulty** | 2/10 |
| **Depends on** | 1.1 |

---

### 1.3 — Auth & Telemetry Middleware
| Field | Detail |
|---|---|
| **Files** | `app/middleware.py` |
| **Responsibility** | `TelemetryMiddleware` captures per-request metadata (model, cache_hit, latency) into `request.state` before handing off to the route handler. |
| **Why separate** | Middleware lifecycle (before/after request) is distinct from route handlers. Must study before the request flow. |
| **Difficulty** | 4/10 |
| **Depends on** | 1.1, 1.2 |

---

### 1.4 — App Lifespan & Dependency Wiring
| Field | Detail |
|---|---|
| **Files** | `app/main.py` lines 32–114 (the `lifespan` context manager) |
| **Responsibility** | Initializes all singletons (ProxyClient, Embedder, VectorStore, Redis, SemanticCache, ModelRouter, ThresholdManager, OTel) and attaches them to `app.state`. |
| **Why separate** | The wiring layer — reveals the full dependency graph of the system before any business logic. |
| **Difficulty** | 5/10 |
| **Depends on** | 1.1, 1.2, 1.3 |

---

### 1.5 — Health Check & Admin Routing
| Field | Detail |
|---|---|
| **Files** | `app/main.py` (`/health`, `include_router`, static dashboard mount) |
| **Responsibility** | Registers `/health`, admin sub-router, and `/dashboard` static mount. No core business logic. |
| **Why separate** | Clean entry point to understand FastAPI routers and mounts before the complexity of cache/proxy logic. |
| **Difficulty** | 2/10 |
| **Depends on** | 1.4 |

---

### 1.6 — Non-Streaming Chat Completions Route
| Field | Detail |
|---|---|
| **Files** | `app/main.py` lines ~175–267 (`/v1/chat/completions` non-streaming path) |
| **Responsibility** | Full pipeline: route → compress → cache lookup → forward/cache-store → telemetry state. Returns `JSONResponse`. |
| **Why separate** | Most complex route in the codebase — calls 5 subsystems in sequence. Study only after all subsystems are understood. |
| **Difficulty** | 7/10 |
| **Depends on** | 1.1–1.5, all of 2.x and 3.x |

---

### 1.7 — SSE Streaming Route
| Field | Detail |
|---|---|
| **Files** | `app/main.py` stream branch (lines ~183–194), `app/proxy.py` `forward_stream` |
| **Responsibility** | Returns `StreamingResponse` backed by an async SSE generator. Bypasses cache and compression entirely. |
| **Why separate** | SSE is a distinct protocol mode. `AsyncGenerator` + `StreamingResponse` is its own conceptual pattern. |
| **Difficulty** | 6/10 |
| **Depends on** | 1.6, 2.4 |

---

## Phase 2 — Multi-Provider Proxy + Failover + Tool Translation

### 2.1 — Provider Model Name Resolution
| Field | Detail |
|---|---|
| **Files** | `app/proxy.py` — `_get_litellm_model`, `_KNOWN_PREFIXES`, `_PREFIX_BY_STEM` (lines 102–174) |
| **Responsibility** | Converts bare model names (`gpt-4o`) to fully-qualified LiteLLM strings (`openai/gpt-4o`) via prefix lookup, stem matching, and API key inference. |
| **Why separate** | Self-contained resolution algorithm. Misunderstanding it breaks all upstream routing silently. |
| **Difficulty** | 3/10 |
| **Depends on** | 1.1 |

---

### 2.2 — LiteLLM Router Initialization (Model List + Fallback Chains)
| Field | Detail |
|---|---|
| **Files** | `app/proxy.py` — `_build_model_list`, `_build_fallback_map`, `ProxyClient.__init__` (lines 200–226) |
| **Responsibility** | Builds a deployment list (which providers/models are active) and explicit fallback chains (gpt-4o → claude → gemini) from available API keys. |
| **Why separate** | The backbone of multi-provider support. Essential for "how do you handle provider failover?" interviews. |
| **Difficulty** | 5/10 |
| **Depends on** | 2.1 |

---

### 2.3 — Non-Streaming Forward (`forward` / `simple_completion`)
| Field | Detail |
|---|---|
| **Files** | `app/proxy.py` — `ProxyClient.forward`, `ProxyClient.simple_completion` (lines 372–455) |
| **Responsibility** | Calls `router.acompletion()` for a single completion. Returns OpenAI-compatible dict. `simple_completion` is the leaner internal variant used by the compressor. |
| **Why separate** | Core proxy path — every non-streaming request flows through here. Study separately from streaming. |
| **Difficulty** | 4/10 |
| **Depends on** | 2.2 |

---

### 2.4 — SSE Streaming Forward (`forward_stream`)
| Field | Detail |
|---|---|
| **Files** | `app/proxy.py` — `ProxyClient.forward_stream` (lines 394–414) |
| **Responsibility** | Calls `router.acompletion(stream=True)`, iterates async chunk generator, yields SSE-formatted strings, ends with `data: [DONE]`. |
| **Why separate** | Streaming changes the response model entirely — async iteration over chunks vs. a single awaitable. |
| **Difficulty** | 5/10 |
| **Depends on** | 2.3 |

---

### 2.5 — Failover & Retry Mechanics
| Field | Detail |
|---|---|
| **Files** | `app/proxy.py` — `_build_fallback_map`, `UpstreamError`, `_map_error`, Router `num_retries` (lines 278–356) |
| **Responsibility** | LiteLLM Router retries up to `num_retries`, then walks the explicit fallback chain. `UpstreamError` + `_map_error` normalize all provider exceptions. |
| **Why separate** | Resilience pattern — retry strategy, exception normalization, and fallback traversal each merit isolated study and have high interview value. |
| **Difficulty** | 6/10 |
| **Depends on** | 2.2, 2.3 |

---

### 2.6 — Tool/Function-Call Translation Guard
| Field | Detail |
|---|---|
| **Files** | `app/proxy.py` — `forward_with_tools`, `_TOOL_UNSUPPORTED_PROVIDERS` (lines 135–143, 457–502) |
| **Responsibility** | Blocks tool requests to unsupported providers with a clear HTTP 400 before the upstream call. LiteLLM handles auto-translation for supported providers. |
| **Why separate** | Tool calling is an optional feature mode. The "capability guard before delegation" pattern is worth studying separately. |
| **Difficulty** | 5/10 |
| **Depends on** | 2.3 |

---

### 2.7 — Admin API Endpoints
| Field | Detail |
|---|---|
| **Files** | `app/api/admin.py` |
| **Responsibility** | Read-only REST endpoints (cost reporting, request log, provider stats). Reads telemetry/SQLite and exposes via admin sub-router. |
| **Why separate** | Lightest sub-phase — a clean view layer over telemetry data. Good to study last in Phase 2. |
| **Difficulty** | 3/10 |
| **Depends on** | 2.2, Phase 4 (telemetry) |

---

## Phase 3 — Semantic Cache + Vector Store + Adaptive Threshold + Router + Compressor

### 3.1 — Embedding Pipeline
| Field | Detail |
|---|---|
| **Files** | `app/embedder.py` |
| **Responsibility** | Wraps `sentence-transformers` to expose `embed(text) → np.ndarray`, `messages_to_text()`, and `content_hash()`. |
| **Why separate** | Entry point to the entire semantic stack. Every other Phase 3 unit depends on its output vector. |
| **Difficulty** | 3/10 |
| **Depends on** | 1.1 |

---

### 3.2 — FAISS Vector Store (ANN Index)
| Field | Detail |
|---|---|
| **Files** | `app/vector_store.py` |
| **Responsibility** | Wraps FAISS `IndexFlatIP`. Provides `add(vector, key)`, `search(vector, k) → [(key, score)]`, `remove_by_key`, `flush`, `persist`/`load`. |
| **Why separate** | Most technically unique component — in-memory ANN search with cosine similarity via inner product on normalized vectors. |
| **Difficulty** | 7/10 |
| **Depends on** | 3.1 |

---

### 3.3 — Semantic Cache Orchestrator (Redis + FAISS)
| Field | Detail |
|---|---|
| **Files** | `app/cache.py` |
| **Responsibility** | Coordinates two-layer cache: embed → FAISS search → threshold check → Redis fetch (hit) or Redis+FAISS store (miss). Also handles `invalidate`, `flush`, `stats`. |
| **Why separate** | Ties embedder + FAISS + Redis together. The lookup/store algorithm is the single most important talking point for the entire project. |
| **Difficulty** | 7/10 |
| **Depends on** | 3.1, 3.2 |

---

### 3.4 — Prompt Complexity Classifier & Model Router
| Field | Detail |
|---|---|
| **Files** | `app/router.py` |
| **Responsibility** | Classifies prompt as SIMPLE/COMPLEX using token count + keyword signals from a YAML rules file. Selects the model tier. Returns `RoutingDecision`. |
| **Why separate** | Rule-based NLP classification + YAML-driven config is an independent concept with its own priority chain logic. |
| **Difficulty** | 5/10 |
| **Depends on** | 1.1 |

---

### 3.5 — Context Compressor
| Field | Detail |
|---|---|
| **Files** | `app/compressor.py` |
| **Responsibility** | When total tokens exceed `compress_threshold`, splits messages into (system, old turns, recent), summarizes old turns via LLM, returns compressed list + ratio metadata. |
| **Why separate** | Uses tiktoken, calls `proxy_client.simple_completion` internally, has a two-gate trigger. Bridges proxy and semantic layers. |
| **Difficulty** | 6/10 |
| **Depends on** | 3.4, 2.3, 1.1 |

---

### 3.6 — Adaptive Threshold Auto-Tuner
| Field | Detail |
|---|---|
| **Files** | `app/adaptive.py` |
| **Responsibility** | Reads recent cache hit rates from SQLite, adjusts similarity threshold ±0.01 (>60% hit → raise, <20% → lower). Stores history in SQLite. |
| **Why separate** | Closed-loop feedback control is a distinct algorithmic concept. Isolated in one file, depends only on SQLite. |
| **Difficulty** | 6/10 |
| **Depends on** | 3.3, 1.1 |

---

### 3.7 — Full Pipeline Integration (Capstone)
| Field | Detail |
|---|---|
| **Files** | `app/main.py` lines 175–265 (orchestrated call chain inside `/v1/chat/completions`) |
| **Responsibility** | How `ModelRouter.route()`, `compress_context()`, `get_active_threshold()`, `SemanticCache.lookup()`, and `ProxyClient.forward()` are chained in the correct order. |
| **Why separate** | Not new code — but understanding *why* the call order is route → compress → cache → forward is its own system design learning objective. |
| **Difficulty** | 8/10 |
| **Depends on** | 1.6, 3.1–3.6, 2.3 |

---

## Meta-Study Guide

### Recommended Linear Study Order

```
1.1 → 1.2 → 1.3 → 1.4 → 1.5
  → 2.1 → 2.2 → 2.3 → 2.5 → 2.4 → 2.6 → 2.7
  → 3.1 → 3.2 → 3.3 → 3.4 → 3.5 → 3.6 → 3.7
  → 1.6 → 1.7
```

---

### Core / Highest-Value Sub-Phases

| Sub-Phase | Why Core |
|---|---|
| **3.3** Semantic Cache Orchestrator | Defining feature of the project |
| **3.2** FAISS Vector Store | Most technically unique component |
| **2.2** LiteLLM Router Init | Multi-provider failover backbone |
| **2.5** Failover & Retry | Highest resilience engineering interview signal |
| **3.7** Full Pipeline Integration | Demonstrates system-level understanding |
| **1.6** Non-Streaming Chat Route | Entire pipeline assembled in one function |

---

### Sub-Phases Understandable Independently

| Sub-Phase | Why Independent |
|---|---|
| **1.1** Config | No imports from app code |
| **1.2** Models | Pure Pydantic, no business logic |
| **2.1** Model Name Resolution | Pure function, no async, no I/O |
| **3.1** Embedder | Thin library wrapper, minimal deps |
| **3.4** Model Router | Rule-based classifier, YAML config only |
| **3.6** Adaptive Threshold | One file, one class, reads SQLite only |

---

### Request-to-Response Dependency Flow

```
Incoming HTTP Request
        │
        ▼
[1.3] TelemetryMiddleware ──── wraps entire request lifecycle
        │
        ▼
[1.5] Route matched → POST /v1/chat/completions
        │
        ▼
[3.4] ModelRouter.route() ────────── token count + keywords → SIMPLE/COMPLEX tier
        │
        ▼
[3.5] compress_context() ─────────── tiktoken gate → LLM summarize old turns
        │
        ▼
[3.6] get_active_threshold() ──────── adaptive or static similarity floor
        │
        ▼
[3.1] Embedder.embed() ────────────── sentence-transformer → float vector
        │
        ▼
[3.2] VectorStore.search() ───────── FAISS ANN → (cache_key, similarity_score)
        │
        ├── score ≥ threshold ──▶ Redis.get(cache_key) ──▶ Cache HIT → return
        │
        └── score < threshold ──▶ Cache MISS
                                          │
                                          ▼
                                  [2.2] LiteLLM Router (registered deployments)
                                          │
                                  [2.5] retry (num_retries=2) + fallback chain
                                          │
                                  [2.3] ProxyClient.forward() → upstream LLM
                                          │
                                  [3.3] SemanticCache.store() → Redis + FAISS
                                          │
                                          ▼
                                  Cache MISS response returned
        │
        ▼
[1.3] TelemetryMiddleware (after) ─── writes request.state to SQLite
        │
        ▼
HTTP Response → client
```
