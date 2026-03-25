# ContextForge

> **Drop-in proxy for LLM apps — cuts costs with semantic caching, smart model routing, and context compression. Zero code changes required.**

[![CI](https://github.com/aayush-1o/contextforge/actions/workflows/ci.yml/badge.svg)](https://github.com/aayush-1o/contextforge/actions/workflows/ci.yml)
![Python 3.11](https://img.shields.io/badge/python-3.11-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)
![Docker](https://img.shields.io/badge/docker-ready-blue)

---

## What Is ContextForge?

ContextForge sits between your app and LLM providers like OpenAI or Anthropic. Your app talks to ContextForge exactly the same way it talks to OpenAI — same API, same SDK, same everything. Behind the scenes, ContextForge caches similar questions so you don't pay twice, routes simple prompts to cheaper models, and compresses long conversations to save tokens. You point your app at `localhost:8000` instead of `api.openai.com`, and your costs go down without changing a single line of code.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Your App / SDK                           │
│              POST http://localhost:8000/v1/chat/completions     │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                     ContextForge Gateway                        │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Optimization Pipeline                       │   │
│  │                                                          │   │
│  │  1. Semantic Cache Lookup (FAISS + Redis)                │   │
│  │     ├─ HIT  → return cached response immediately        │   │
│  │     └─ MISS → continue ↓                                │   │
│  │                                                          │   │
│  │  2. Model Router (rule-based classifier)                 │   │
│  │     ├─ SIMPLE  → gpt-3.5-turbo / claude-haiku           │   │
│  │     └─ COMPLEX → gpt-4o / claude-opus                   │   │
│  │                                                          │   │
│  │  3. Proxy Forward (OpenAI SDK)                           │   │
│  │     └─ send to upstream with routed model                │   │
│  │                                                          │   │
│  │  4. Cache Store                                          │   │
│  │     └─ embed response + store in FAISS & Redis           │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Response ← with X-Model-Tier + X-Model-Selected headers       │
└─────────────────────────────────────────────────────────────────┘
```

---

## How It Works

1. **Your app sends a request** to ContextForge, just like it would to OpenAI.
2. **Cache check** — ContextForge embeds the prompt and searches for similar past questions. If a match is found (≥92% similarity), the cached response is returned instantly.
3. **Model routing** — If no cache hit, the router classifies the prompt as simple or complex using keyword signals and token count, then picks the cheapest model that can handle it.
4. **Upstream call** — The request is forwarded to the selected model at OpenAI (or Anthropic).
5. **Cache store** — The response is saved in Redis and the embedding is indexed in FAISS for future lookups.
6. **Response returned** — Your app gets back a standard OpenAI-format response, plus headers showing which model was used and why.

---

## Current Status

| Phase | Feature | Status |
|-------|---------|--------|
| 0 | Architecture & Repo Setup | ✅ Complete |
| 1 | Core Proxy (Passthrough) | ✅ Complete |
| 2 | Semantic Cache | ✅ Complete |
| 3 | Model Router | ✅ Complete |
| 4 | Context Compressor | 🔄 In Progress |
| 5 | Telemetry Layer | ⏳ Pending |
| 6 | Adaptive Thresholds & Cache Invalidation | ⏳ Pending |
| 7 | Testing & Benchmarking Harness | ⏳ Pending |
| 8 | Dockerization & Deployment | ⏳ Pending |
| 9 | Final Documentation & Handoff | ⏳ Pending |

**Current version:** `v0.3.0` · **Tests:** 44/44 passing · **Lint:** ruff clean

---

## Quick Start

### Prerequisites

- Docker & Docker Compose
- An OpenAI API key (and/or Anthropic)

### Setup

```bash
# 1. Clone the repo
git clone https://github.com/aayush-1o/contextforge.git
cd contextforge

# 2. Configure environment
cp .env.example .env
nano .env   # paste your OPENAI_API_KEY

# 3. Start everything
docker compose up --build -d

# 4. Verify it's running
curl http://localhost:8000/health
# → {"status":"ok","version":"0.3.0"}
```

### Point Your App at ContextForge

```python
import openai

client = openai.OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="your-openai-key",
)

response = client.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": "What is the capital of France?"}],
)

print(response.choices[0].message.content)
```

That's it. Your existing code works unchanged.

---

## Configuration

All settings are in `.env` (copy from `.env.example`):

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | Your OpenAI API key | *(required)* |
| `ANTHROPIC_API_KEY` | Your Anthropic API key | `""` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379` |
| `SIMILARITY_THRESHOLD` | Cosine similarity threshold for cache hits (0.0–1.0) | `0.92` |
| `CACHE_TTL_SECONDS` | How long cached responses live in Redis | `86400` (24h) |
| `PREFERRED_PROVIDER` | Which LLM provider to use: `openai` or `anthropic` | `openai` |
| `LOG_LEVEL` | Logging verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR` | `INFO` |
| `SQLITE_DB_PATH` | Path for the telemetry SQLite database | `./data/telemetry.db` |
| `FAISS_INDEX_PATH` | Path for the FAISS vector index file | `./data/faiss.index` |
| `OPENAI_BASE_URL` | Override OpenAI API base URL (for proxies/testing) | `https://api.openai.com/v1` |
| `CONTEXT_COMPRESSION_THRESHOLD_TOKENS` | Token count above which compression activates (Phase 4) | `2000` |
| `COMPRESSION_MIN_TURNS` | Minimum conversation turns before compression (Phase 4) | `6` |

---

## API Reference

### `POST /v1/chat/completions`

OpenAI-compatible chat completions endpoint. Supports both streaming and non-streaming.

**Request:**
```json
{
  "model": "gpt-3.5-turbo",
  "messages": [
    {"role": "user", "content": "What is the capital of France?"}
  ],
  "temperature": 0.7,
  "stream": false
}
```

**Response (non-streaming):**
```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1700000000,
  "model": "gpt-3.5-turbo-0125",
  "choices": [
    {
      "index": 0,
      "message": {"role": "assistant", "content": "The capital of France is Paris."},
      "finish_reason": "stop"
    }
  ],
  "usage": {"prompt_tokens": 14, "completion_tokens": 8, "total_tokens": 22}
}
```

**Response headers:**
| Header | Description |
|--------|-------------|
| `X-Model-Tier` | Classification result: `simple` or `complex` |
| `X-Model-Selected` | The model actually used for the upstream call |
| `X-Cache-Hit` | `true` if the response came from cache |

**Special request headers:**
| Header | Description |
|--------|-------------|
| `X-ContextForge-Model-Override` | Force a specific model, bypassing the router (e.g. `gpt-4o`) |
| `X-ContextForge-No-Compress` | Skip context compression (Phase 4, not yet implemented) |

### `GET /health`

Health check endpoint.

**Response:**
```json
{
  "status": "ok",
  "version": "0.3.0"
}
```

---

## Project Structure

```
contextforge/
├── app/
│   ├── main.py             # FastAPI app + lifespan (startup/shutdown)
│   ├── proxy.py            # Upstream forwarding via OpenAI SDK
│   ├── models.py           # Pydantic request/response schemas
│   ├── config.py           # Pydantic Settings (loads .env, @lru_cache)
│   ├── cache.py            # Semantic cache orchestrator (FAISS + Redis)
│   ├── embedder.py         # Sentence-transformer embedding wrapper
│   ├── vector_store.py     # FAISS index with thread-safe writes + persistence
│   ├── router.py           # Rule-based complexity classifier (tiktoken + keywords)
│   ├── compressor.py       # [Phase 4] Context compression — stub
│   ├── telemetry.py        # [Phase 5] Per-request telemetry — stub
│   └── middleware.py        # [Phase 5] Request wrapping middleware — stub
├── config/
│   └── routing_rules.yaml  # Token thresholds, keywords, model tier mappings
├── tests/
│   ├── conftest.py         # Shared fixtures: mock Redis, FAISS, proxy, router
│   ├── test_proxy.py       # 12 tests: health, completions, streaming, errors
│   ├── test_cache.py       # 14 tests: VectorStore, SemanticCache, endpoints
│   ├── test_router.py      # 18 tests: classifier, 1000-prompt accuracy, integration
│   ├── test_compressor.py  # [Phase 4] Compression tests — stub
│   └── test_telemetry.py   # [Phase 5] Telemetry tests — stub
├── benchmarks/
│   └── prompts_labeled.json  # 1000 labeled prompts for router accuracy testing
├── fixtures/
│   └── openai_responses/   # Recorded API response fixtures
│       ├── chat_completion_success.json   # Streaming + non-streaming
│       ├── chat_completion_errors.json    # 429, 500, 401, 400, 504
│       ├── chat_completion.json           # Legacy non-streaming
│       ├── chat_completion_stream.json    # Legacy stream chunks
│       └── error_429.json                 # Legacy 429 error
├── docs/
│   ├── ARCHITECTURE.md     # System design + ADRs + component diagram
│   └── HANDOFF.md          # Onboarding guide for next developer
├── .github/workflows/
│   └── ci.yml              # GitHub Actions: ruff lint + pytest
├── docker-compose.yml      # App + Redis services
├── Dockerfile              # Python 3.11 slim container
├── requirements.txt        # Pinned Python dependencies
├── .env.example            # Template for environment variables
├── DECISIONS.md            # Architecture Decision Records (ADR-001 to ADR-004)
├── CHANGELOG.md            # Version history
├── CONTRIBUTING.md         # Contribution guidelines
└── README.md               # This file
```

---

## Tech Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| Web framework | FastAPI (Python 3.11) | Async-first, OpenAPI auto-docs, fast |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2 | CPU-fast, 384-dim, no GPU needed |
| Vector search | FAISS (IndexFlatIP) | In-process, zero infra, fast for <100K vectors |
| Cache store | Redis 7 | TTL support, fast KV reads, production-proven |
| Token counting | tiktoken | Model-specific token counts, fast |
| Telemetry DB | SQLite (via SQLModel) | Zero infra, single-file, easy migration path |
| LLM SDKs | openai-python + anthropic-python | Official SDKs, version-pinned |
| Config | Pydantic Settings + .env | Type-safe, validated at startup |
| Logging | structlog | Structured JSON logs, easy to parse |
| Testing | pytest + httpx | Fixture-based, no live API calls |
| Containerization | Docker + Docker Compose | One-command local deployment |
| Linting | ruff | Fast, replaces flake8 + isort + pyupgrade |

---

## Running Tests

```bash
# Install dependencies (in a virtual environment)
pip install -r requirements.txt

# Run lint check
ruff check app/ tests/ benchmarks/

# Run all tests
pytest tests/ -v
```

| Test file | Tests | What it covers |
|-----------|-------|----------------|
| `test_proxy.py` | 12 | Health check, non-streaming completions, streaming SSE, error propagation (429/500/502) |
| `test_cache.py` | 14 | VectorStore CRUD, SemanticCache hit/miss, Redis TTL, FAISS-Redis sync, endpoint integration |
| `test_router.py` | 18 | Classifier unit tests, ≥85% accuracy on 1000-prompt labeled set, override header, endpoint integration |

**All 44 tests pass without any live API calls or running services.**

---

## Contributing

### Branch Naming

| Pattern | Use |
|---------|-----|
| `phase/<N>-<name>` | Phase feature branches (e.g. `phase/4-compressor`) |
| `docs/<description>` | Documentation-only changes |
| `fix/<description>` | Bug fixes |
| `refactor/<description>` | Non-functional improvements |

### PR Rules

1. Branch from `develop` (never directly from `main`).
2. Write tests for every new feature — no untested code.
3. `ruff check app/ tests/ benchmarks/` must pass with zero errors.
4. `pytest tests/ -v` must pass with zero failures.
5. Open PR against `develop`. Merges to `main` happen via `develop` only.

### Definition of Done

A feature is "done" when:
- [ ] Code is implemented and lint-clean
- [ ] Tests are written and passing
- [ ] Existing tests still pass (no regressions)
- [ ] Documentation is updated
- [ ] PR is reviewed and merged into `develop`
- [ ] Version is tagged on `main`

---

## Roadmap

| Phase | What's Coming | Summary |
|-------|--------------|---------|
| **4** | Context Compressor | Summarize long conversation histories before forwarding to reduce token usage. Uses the LLM itself to compress old messages while preserving meaning. |
| **5** | Telemetry Layer | Track every request in SQLite: model used, latency, cost estimate, cache hit, compression ratio. Dashboard-ready data. |
| **6** | Adaptive Thresholds & Cache Invalidation | Auto-tune similarity thresholds based on hit rates. Add API endpoints to manually invalidate cached entries. |
| **7** | Testing & Benchmarking Harness | End-to-end benchmark suite measuring cache hit rates, routing accuracy, latency percentiles, and cost savings. |
| **8** | Dockerization & Deployment | Production-ready Docker images, health checks, volume management, optional GPU support for embeddings. |
| **9** | Final Documentation & Handoff | Complete API docs, deployment guide, architecture diagrams, and contributor onboarding. |

---

## License

MIT
