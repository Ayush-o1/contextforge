# ContextForge

**An OpenAI-compatible LLM proxy middleware built with Python/FastAPI.**

Point your app at `localhost:8000` instead of `api.openai.com`. ContextForge sits in between, applying semantic caching, rule-based model routing, and context compression before forwarding requests through LiteLLM to 100+ providers.

[![CI](https://github.com/Ayush-o1/contextforge/actions/workflows/ci.yml/badge.svg)](https://github.com/Ayush-o1/contextforge/actions/workflows/ci.yml)
![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

---

## What It Does

1. **Model routing** — classifies each prompt as `simple` or `complex` using token count and keyword rules, then selects the appropriate model tier (e.g. `gpt-3.5-turbo` vs `gpt-4o`). Configurable via `config/routing_rules.yaml`.

2. **Context compression** — when a conversation exceeds a token threshold (default: 2,000 tokens) and has enough turns (default: 6), older messages are summarized via an LLM call, reducing upstream token usage.

3. **Semantic caching** — prompts are embedded using `all-MiniLM-L6-v2` and searched against a FAISS index. On a match above the cosine similarity threshold (default: 0.92), the cached response is returned from Redis without an upstream API call.

4. **LiteLLM forwarding** — cache misses are forwarded to the LLM provider through LiteLLM Router, which handles auth, retries, and automatic failover across providers.

5. **Telemetry** — every request is logged to a local SQLite database (model, latency, cost, cache hit, compression). An admin API and a static HTML dashboard visualize this data.

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Web framework | FastAPI (Python 3.11) + Uvicorn |
| LLM gateway | LiteLLM Router |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` (384-dim, CPU) |
| Vector search | FAISS (`IndexFlatIP`) |
| Cache store | Redis 7 |
| Token counting | tiktoken |
| Telemetry DB | SQLite (raw `sqlite3`, two tables) |
| Config | Pydantic Settings + `.env` |
| Logging | structlog (structured JSON) |
| Testing | pytest + httpx (no live API calls required) |
| Linting | ruff |
| Containerization | Docker + Docker Compose |

---

## Architecture

```
Your App
    |
    v  POST /v1/chat/completions
ContextForge (FastAPI)
    |
    +-- 1. ModelRouter         -- token count + keyword -> simple/complex tier
    +-- 2. compress_context()  -- summarize old turns if token threshold exceeded
    +-- 3. SemanticCache.lookup() -- embed prompt -> FAISS search -> Redis fetch
    |       +-- HIT  -> return cached response (no upstream call)
    |       +-- MISS -> forward to LiteLLM Router
    |                    +-- LiteLLM -> Provider API (OpenAI/Anthropic/Gemini/etc.)
    +-- 4. SemanticCache.store() -- embed + store in FAISS + Redis
    +-- 5. TelemetryMiddleware  -- write request record to SQLite
```

**Streaming requests** (`"stream": true`) bypass cache and compression and are forwarded directly.

**Adaptive threshold** — `ThresholdManager` periodically adjusts the FAISS similarity threshold up or down based on observed cache hit rates from the telemetry table.

---

## Project Structure

```
contextforge/
├── app/
│   ├── main.py              # FastAPI app, lifespan, all route handlers
│   ├── proxy.py             # LiteLLM Router client, streaming, tool-call guard
│   ├── router.py            # Rule-based complexity classifier (ModelRouter)
│   ├── compressor.py        # Context compression (summarize old turns)
│   ├── cache.py             # SemanticCache -- coordinates FAISS + Redis
│   ├── embedder.py          # Sentence-transformer embedding wrapper
│   ├── vector_store.py      # FAISS index with thread-safe writes + persistence
│   ├── adaptive.py          # Adaptive similarity threshold (ThresholdManager)
│   ├── telemetry.py         # SQLite writer/reader (telemetry + request_log tables)
│   ├── costs.py             # Per-model cost estimation (static fallback table)
│   ├── models.py            # Pydantic schemas (ChatCompletionRequest, responses)
│   ├── config.py            # Pydantic Settings (loads .env)
│   ├── middleware.py        # TelemetryMiddleware -- writes per-request record
│   └── api/
│       └── admin.py         # /admin/usage, /admin/logs, /admin/savings
├── config/
│   └── routing_rules.yaml   # Token thresholds, keywords, model-tier mappings
├── docs/
│   ├── dashboard/           # Static HTML/CSS/JS telemetry dashboard
│   │   └── index.html       # Open in browser; auto-connects to running backend
│   └── assets/              # Screenshots
├── tests/                   # pytest suite (no live API calls)
│   ├── conftest.py          # Shared fixtures (mock Redis, FAISS)
│   ├── test_proxy.py
│   ├── test_cache.py
│   ├── test_router.py
│   ├── test_compressor.py
│   ├── test_telemetry.py
│   ├── test_adaptive.py
│   ├── test_cache_invalidation.py
│   ├── test_benchmarks.py
│   ├── test_tool_use.py
│   ├── test_failover.py
│   └── test_phase3.py
├── benchmarks/
│   ├── run_benchmark.py     # E2E benchmark runner (requires running server)
│   ├── benchmark_utils.py
│   └── prompts_labeled.json # 1,000 labeled prompts for routing accuracy tests
├── .github/workflows/
│   ├── ci.yml               # Lint + test on push/PR
│   └── deploy.yml           # Railway deployment
├── docker-compose.yml       # App + Redis
├── Dockerfile               # Multi-stage Python 3.11 image
├── requirements.txt
├── pyproject.toml           # ruff + pytest config
└── .env.example             # All environment variables with comments
```

---

## Local Setup

### Prerequisites

- Python 3.11+
- Redis (required for the semantic cache)
- At least one LLM provider API key

### Option A: Docker (simplest)

```bash
git clone https://github.com/Ayush-o1/contextforge.git
cd contextforge

cp .env.example .env
# Edit .env -- add your OPENAI_API_KEY (or any other provider key)

docker compose up --build -d

curl http://localhost:8000/health
# -> {"status":"ok","version":"1.0.0"}
```

### Option B: Local development

```bash
git clone https://github.com/Ayush-o1/contextforge.git
cd contextforge

python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env -- add at least one LLM provider API key

# Start Redis separately
docker run -d -p 6379:6379 redis:7-alpine

# Run the server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Usage

No code changes needed. Change the `base_url` in your existing OpenAI SDK calls:

```python
import openai

client = openai.OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="your-api-key",
)

response = client.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": "What is the capital of France?"}],
)
print(response.choices[0].message.content)
```

Responses include diagnostic headers:

| Header | Value |
|--------|-------|
| `X-Cache` | `HIT` or `MISS` |
| `X-Similarity` | Cosine similarity score (on cache hit) |
| `X-Model-Tier` | `simple` or `complex` |
| `X-Model-Selected` | Actual model used (e.g. `gpt-4o`) |
| `X-Compressed` | `True` if context compression ran |
| `X-Compression-Ratio` | Ratio of compressed to original tokens |

---

## Environment Variables

Copy `.env.example` to `.env` and fill in your keys. Key variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | `""` | Required if using OpenAI models |
| `ANTHROPIC_API_KEY` | `""` | For Anthropic/Claude models |
| `GEMINI_API_KEY` | `""` | For Google Gemini models |
| `GROQ_API_KEY` | `""` | For Groq-hosted models |
| `SIMPLE_MODEL` | `gpt-3.5-turbo` | Model used for simple-tier routing |
| `COMPLEX_MODEL` | `gpt-4o` | Model used for complex-tier routing |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection string |
| `SIMILARITY_THRESHOLD` | `0.92` | Cosine similarity required for a cache hit |
| `CACHE_TTL_SECONDS` | `86400` | Cache entry lifetime (seconds) |
| `COMPRESS_THRESHOLD` | `2000` | Token count that triggers compression |
| `COMPRESS_MIN_TURNS` | `6` | Minimum conversation turns before compression |
| `COMPRESS_KEEP_RECENT` | `4` | Recent turns kept verbatim during compression |
| `ADAPTIVE_THRESHOLD_ENABLED` | `true` | Auto-adjust similarity threshold from telemetry |
| `TEST_MODE` | `false` | Forces simple model for all requests |
| `ENABLE_OTEL` | `false` | Enable OpenTelemetry tracing (OTLP gRPC) |
| `OTEL_ENDPOINT` | `http://localhost:4317` | OTLP collector endpoint |

Full reference: [docs/CONFIGURATION.md](docs/CONFIGURATION.md)

---

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/v1/chat/completions` | OpenAI-compatible chat completions |
| `GET` | `/health` | Health check |
| `GET` | `/v1/telemetry` | Paginated telemetry records |
| `GET` | `/v1/telemetry/summary` | Aggregated stats |
| `GET` | `/v1/threshold` | Current adaptive threshold info |
| `POST` | `/v1/threshold/evaluate` | Trigger threshold re-evaluation |
| `GET` | `/v1/cache/stats` | FAISS vector count + Redis key count |
| `DELETE` | `/v1/cache` | Flush entire cache |
| `DELETE` | `/v1/cache/{key}` | Invalidate a specific cache entry |
| `GET` | `/admin/usage` | Aggregated spend/token summary (filterable) |
| `GET` | `/admin/logs` | Paginated raw request log |
| `GET` | `/admin/savings` | Estimated savings from cache + routing |

**Request headers recognized by `/v1/chat/completions`:**

| Header | Description |
|--------|-------------|
| `X-ContextForge-Model-Override` | Force a specific model, bypassing routing |
| `X-ContextForge-No-Compress: true` | Skip context compression for this request |

Full schema reference: [docs/API.md](docs/API.md)

---

## Dashboard

Open `docs/dashboard/index.html` in your browser while the backend is running. It connects to `localhost:8000` and shows live telemetry: request counts, cache hit rate, model distribution, latency trends, and the full request log. Falls back to mock data when the backend is not running.

---

## Testing

All tests use mocked dependencies -- no live API calls or running Redis/server required.

```bash
# Lint
ruff check app/ tests/ benchmarks/

# Run all tests
PYTHONPATH=. pytest tests/ -v
```

| Test file | What it covers |
|-----------|----------------|
| `test_proxy.py` | Health, completions, streaming, error propagation |
| `test_cache.py` | VectorStore CRUD, SemanticCache hit/miss, Redis TTL |
| `test_router.py` | Classifier unit tests, accuracy on labeled prompt set |
| `test_compressor.py` | Token counting, compression trigger, fallback on error |
| `test_telemetry.py` | Write/read roundtrip, summary, cost estimation |
| `test_adaptive.py` | Threshold raise/lower, min/max caps, endpoints |
| `test_cache_invalidation.py` | Flush, invalidate, stats endpoints |
| `test_benchmarks.py` | Paraphrase detection, latency stats, routing accuracy |
| `test_tool_use.py` | Tool-call passthrough, schema translation, multi-provider |
| `test_failover.py` | LiteLLM failover routing, provider retry behavior |
| `test_phase3.py` | End-to-end router integration |

### Benchmarks

The `benchmarks/` directory contains an E2E benchmark runner that measures routing accuracy and cache hit rates against a 1,000-prompt labeled dataset. Requires a running server:

```bash
python benchmarks/run_benchmark.py          # full run (server + Redis required)
python benchmarks/run_benchmark.py --dry-run  # safe for CI, no server needed
```

---

## Important Implementation Notes

### Database schema

Two SQLite tables are created in `./data/telemetry.db` at startup:

- **`telemetry`** — written by `TelemetryMiddleware` after every request. Columns: `model_requested`, `model_used`, `cache_hit`, `similarity_score`, `prompt_tokens`, `completion_tokens`, `estimated_cost_usd`, `latency_ms`, `compressed`, `compression_ratio`.
- **`request_log`** — written by the LiteLLM success callback in `proxy.py`. Only populated on non-cached upstream calls. Contains accurate cost from `litellm.completion_cost()`. Used by `/admin/usage` and `/admin/savings`.

Cache hits never appear in `request_log` (they never reach LiteLLM), but they do appear in `telemetry`.

### FAISS index persistence

The FAISS index is saved to `./data/faiss.index` on shutdown (`SemanticCache.close()` -> `VectorStore.persist()`). It is reloaded from disk on startup if the file exists. In Docker, this path is mapped to a named volume so it survives container restarts.

### Streaming

Streaming requests (`"stream": true`) bypass both context compression and the semantic cache. They are forwarded directly through the LiteLLM Router and returned as SSE.

### Tool calling

The `forward_with_tools()` method in `proxy.py` checks whether the resolved provider supports tool/function calling before making the upstream call. Providers without tool support (`ollama`, `huggingface`, `replicate`) return a 400 with a descriptive error. LiteLLM handles OpenAI-to-provider-native format translation automatically for supported providers.

### Routing rules

`config/routing_rules.yaml` defines token thresholds and keyword lists for the simple/complex classifier. Runtime overrides via `SIMPLE_MODEL` / `COMPLEX_MODEL` env vars take precedence over the YAML model map. Send `X-ContextForge-Model-Override` header to bypass routing entirely for a single request.

---

## Contributors

Built as a student capstone project by:

- [Ayush Kumar](https://github.com/Ayush-o1)
- [Astik](https://github.com/Astik01)
- [Anubhav](https://github.com/Anubhav104401)
- [Aryan Bhat](https://github.com/aryanbhat2109-ctrl)

---

## License

MIT -- see [LICENSE](LICENSE).
