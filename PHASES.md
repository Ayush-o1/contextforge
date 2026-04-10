# ContextForge — Team Phase Assignments

> **Internal document.** This file records the original team phase assignments used during development. It is preserved for historical reference. For contributing, see [CONTRIBUTING.md](CONTRIBUTING.md).

This document defines ownership for the remaining work on ContextForge.
Each person owns their assigned files, implementation, tests, and documentation updates for their phase.

> **Integration rule:** All code is sent to Ayush. Ayush reviews, integrates, commits, and creates the final PR. Do not push directly.

---

## Table of Contents

| Phase | Owner | Area |
|-------|-------|------|
| [Phase 1](#phase-1--api-gateway--openai-compatible-endpoint--streaming) | Ayush | API Gateway + Streaming |
| [Phase 2](#phase-2--multi-provider-proxy--failover--tool-translation) | Ayush | Proxy + Failover + Tool Translation |
| [Phase 3](#phase-3--semantic-cache--adaptive-threshold--model-router) | Ayush | Semantic Cache + Adaptive Threshold + Router |
| [Phase 4](#phase-4--telemetry--cost-tracking) | Anubhav | Telemetry + Cost Tracking |
| [Phase 5](#phase-5--cache-invalidation-api) | Anubhav | Cache Invalidation API |
| [Phase 6](#phase-6--dashboard-frontend) | Astik | Dashboard Frontend |
| [Phase 7](#phase-7--benchmarks--results) | Astik | Benchmarks + Results |
| [Phase 8](#phase-8--documentation) | Astik | Documentation |
| [Phase 9](#phase-9--docker--deployment) | Aryan | Docker + Deployment |
| [Phase 10](#phase-10--cicd--test-expansion) | Aryan | CI/CD + Test Expansion |

---

## Merge Order

```
Phase 1 → Phase 2 → Phase 3   (core — merged first)
        ↓
Phase 4 → Phase 5              (depends on Phase 1+3)
Phase 6                        (depends on Phase 4)
Phase 7                        (depends on Phases 1–3)
Phase 8                        (depends on all)
Phase 9 → Phase 10             (can proceed after Phases 1–3 are runnable)
```

Final pass: full test run + Railway deployment verification.

---

# Ayush

## Phase 1 — API Gateway + OpenAI-Compatible Endpoint + Streaming

### Files

| File | Role |
|------|------|
| `app/main.py` | FastAPI app, all routes, lifespan |
| `app/middleware.py` | CORS, auth, logging middleware |
| `app/models.py` | Pydantic request/response models |
| `app/config.py` | Environment config and settings |

### Tasks

1. Complete `/v1/chat/completions` OpenAI-compatible endpoint behavior
2. Implement and polish SSE streaming with `StreamingResponse`
3. Finalize request validation, auth, middleware, and integration with proxy/cache

### Required Tests

- `tests/test_main.py`
- `tests/test_streaming.py`
- `tests/test_models.py`

---

## Phase 2 — Multi-Provider Proxy + Failover + Tool Translation

### Files

| File | Role |
|------|------|
| `app/proxy.py` | LiteLLM abstraction, provider routing, tool translation |
| `app/api/admin.py` | Admin REST endpoints |

### Tasks

1. Complete LiteLLM integration for all supported providers
2. Implement automatic failover and retry handling
3. Add tool/function-call translation between providers

### Required Tests

- `tests/test_proxy.py`
- `tests/test_failover.py`
- `tests/test_tool_use.py`

---

## Phase 3 — Semantic Cache + Adaptive Threshold + Model Router

### Files

| File | Role |
|------|------|
| `app/cache.py` | Two-layer cache orchestration (Redis + FAISS) |
| `app/vector_store.py` | FAISS index management and ANN search |
| `app/embedder.py` | sentence-transformers embedding pipeline |
| `app/adaptive.py` | Adaptive threshold feedback loop |
| `app/router.py` | Multi-dimensional model routing engine |
| `app/compressor.py` | tiktoken-based context compression |

### Tasks

1. Finalize FAISS + Redis semantic cache pipeline
2. Implement adaptive cache threshold tuning and model routing
3. Complete context compression and connect it into the request flow

### Required Tests

- `tests/test_cache.py`
- `tests/test_router.py`
- `tests/test_adaptive.py`
- `tests/test_compressor.py`

---

# Anubhav

## Phase 4 — Telemetry + Cost Tracking

### Files

| File | Role |
|------|------|
| `app/telemetry.py` | Request telemetry, latency tracking, SQLite analytics |
| `app/costs.py` | Per-provider token cost table, savings estimation |

### Tasks

1. Track request count, latency, cache hits, and provider usage
2. Implement per-request cost estimation and savings calculation
3. Store analytics in SQLite and expose summary functions

### Required Tests

- `tests/test_telemetry.py`
- `tests/test_costs.py`

### Notes

- Do not modify `app/main.py` directly. If middleware hooks are needed, document the required integration point and send to Ayush.
- Cost table lives in `app/costs.py` — keep it provider-agnostic.

---

## Phase 5 — Cache Invalidation API

### Files

| File | Role |
|------|------|
| Cache routes inside `app/main.py` | `DELETE /v1/cache`, `DELETE /v1/cache/{key}`, `GET /v1/cache/stats` |
| Related helpers in `app/cache.py` | Namespace invalidation, TTL management |

### Tasks

1. Complete `DELETE /v1/cache` — full cache wipe
2. Complete `DELETE /v1/cache/{key}` — single key eviction
3. Complete `GET /v1/cache/stats` and namespace invalidation logic

### Required Tests

- `tests/test_cache_invalidation.py`
- `tests/test_cache_stats.py`

### Notes

- Route stubs may already exist in `app/main.py`. Do not reorganize the file — only add to the stub bodies.
- Namespace logic should call helpers in `app/cache.py`, not duplicate Redis logic inline.

---

# Astik

## Phase 6 — Dashboard Frontend

### Files

| File | Role |
|------|------|
| `docs/dashboard/index.html` | Main dashboard page |
| `docs/dashboard/js/*` | Chart.js rendering, API polling, UI logic |
| `docs/dashboard/css/*` | Styles and layout |

### Tasks

1. Build all dashboard pages and connect them to telemetry endpoints
2. Add Chart.js graphs for latency, cache hit rate, cost savings, and provider usage
3. Add loading states and mock fallback when API is unavailable

### Required Tests

- Frontend/manual validation checklist
- Dashboard integration verification with telemetry endpoints

### Notes

- Telemetry endpoints are defined in Phase 4. Use mock data (`fixtures/`) while Phase 4 is in progress.
- Do not hardcode API base URL — read it from a config variable at the top of the JS file.

---

## Phase 7 — Benchmarks + Results

### Files

| File | Role |
|------|------|
| `benchmarks/run_benchmark.py` | Benchmark runner and orchestration |
| `benchmarks/benchmark_utils.py` | Measurement helpers, latency percentiles |
| `benchmarks/prompts_labeled.json` | 1000-prompt labeled dataset |
| `benchmarks/results/` | Output reports directory |

### Tasks

1. Run the 1000-prompt benchmark suite
2. Measure latency, cache hit rate, routing accuracy, and cost savings
3. Export benchmark reports and save final results

### Required Tests

- `tests/test_benchmarks.py`
- Validation of benchmark output format

### Notes

- Results are the property of the whole team — share raw JSON output in addition to the report.
- Do not change `prompts_labeled.json`. If you need additional prompts, create a separate file.

---

## Phase 8 — Documentation

### Files

| File | Role |
|------|------|
| `README.md` | Project overview, setup, quickstart |
| `docs/API.md` | All route references and request/response shapes |
| `docs/ARCHITECTURE.md` | System design, module diagram |
| `docs/SETUP.md` | Local dev setup instructions |
| `docs/TROUBLESHOOTING.md` | Common errors and fixes |
| `CONTRIBUTING.md` | Contributor guidelines |

### Tasks

1. Update setup and usage instructions to match final implementation
2. Document all API routes and environment variables
3. Add architecture diagrams and contributor instructions

### Notes

- Use the existing `docs/ARCHITECTURE.md` as a base — extend, do not rewrite from scratch.
- All curl examples must be tested and working before submission.
- `DECISIONS.md` is maintained by Ayush — do not edit it.

---

# Aryan

## Phase 9 — Docker + Deployment

### Files

| File | Role |
|------|------|
| `Dockerfile` | FastAPI app container build |
| `docker-compose.yml` | Multi-service orchestration (app + Redis) |
| `railway.json` | Railway.app deploy config |
| `docs/DEPLOYMENT.md` | Deployment guide |

### Tasks

1. Finalize Docker setup for FastAPI, Redis, and supporting services
2. Configure Railway deployment and environment handling
3. Add health checks and startup/shutdown scripts

### Required Tests

- Local `docker-compose up` validation
- Deployment verification on Railway (staging environment)

### Notes

- Health check endpoint is `GET /health` — verify it returns `200 OK` before deployment.
- All secrets must come from environment variables; no hardcoded values.
- FAISS index is in-memory — do not attempt to persist it across container restarts.

---

## Phase 10 — CI/CD + Test Expansion

### Files

| File | Role |
|------|------|
| `.github/workflows/*` | GitHub Actions pipeline definitions |
| `pyproject.toml` | Linting config (ruff), test config (pytest) |
| `tests/*` | Full test suite |

### Tasks

1. Complete GitHub Actions workflow for linting (`ruff`) and tests (`pytest`)
2. Add missing integration and end-to-end tests
3. Ensure all tests pass before merge

### Required Tests

- Full repository test run: `pytest tests/ -v`
- CI pipeline validation: all jobs green on a test branch

### Notes

- Do not modify core implementation files — only add tests and CI config.
- If a test requires a live Redis instance, mark it with `@pytest.mark.integration` and skip it in the default CI run.
- `conftest.py` is the shared fixture file — add fixtures there, not inline in individual test files.

---

# Working Rules

1. **Implementation + tests are always bundled.** Do not submit a phase without its required tests.
2. **Stay in your files.** Do not modify files owned by another person unless explicitly agreed upon.
3. **No direct pushes.** Send your completed files to Ayush. Ayush reviews, integrates, and commits.
4. **Stubs first.** If your phase depends on another that isn't done yet, define an interface/stub and keep working.
5. **Integration order is fixed:** Phases 1–3 merge first. Phases 4–10 follow. Final test + deploy pass at the end.
6. **Communicate blockers early.** If your phase is blocked on another person's work, flag it immediately — don't wait.
