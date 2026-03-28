# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/).

---

## [v0.6.0] — 2026-03-27

### Added — Phase 6: Adaptive Thresholds & Cache Invalidation
- Adaptive similarity threshold auto-tuning based on telemetry cache hit rates (`app/adaptive.py`)
  - `ThresholdManager` class with SQLite-backed `threshold_history` table
  - Hit rate > 60% → raise threshold by 0.01 (cap at 0.98)
  - Hit rate < 20% → lower threshold by 0.01 (floor at 0.70)
  - `get_active_threshold()` helper for runtime threshold resolution
- `GET /v1/threshold` endpoint — returns current threshold, baseline, and last evaluation time
- `POST /v1/threshold/evaluate` endpoint — manually triggers threshold evaluation
- Cache invalidation API:
  - `DELETE /v1/cache` — flush entire cache (FAISS vectors + Redis keys), idempotent
  - `DELETE /v1/cache/{key}` — invalidate a specific cached entry
  - `GET /v1/cache/stats` — returns vector count, Redis key count, and active similarity threshold
- `VectorStore.flush()` method — resets index, clears id_map, removes persisted files
- `VectorStore.remove_by_key()` method — targeted vector removal via FAISS `remove_ids`
- `SemanticCache.invalidate()`, `SemanticCache.flush()`, and `SemanticCache.stats()` methods
- Optional `threshold` parameter on `SemanticCache.lookup()` for adaptive override
- 4 new config settings: `ADAPTIVE_THRESHOLD_ENABLED`, `ADAPTIVE_THRESHOLD_WINDOW`, `ADAPTIVE_THRESHOLD_MIN`, `ADAPTIVE_THRESHOLD_MAX`
- 15 new tests: 8 adaptive threshold tests + 7 cache invalidation tests (69 total)

---

## [v0.5.0] — 2026-03-27

### Added — Phase 5: Telemetry Layer
- SQLite-based per-request telemetry with WAL mode for concurrent writes
- `GET /v1/telemetry` endpoint with pagination (limit, offset)
- `GET /v1/telemetry/summary` endpoint with aggregated stats (cache hit rate, avg latency, total cost, p95 latency)
- Per-model cost estimation via `app/costs.py`
- Request middleware (`app/middleware.py`) for telemetry state tracking
- `TelemetryDB` class and `TelemetryRecord` dataclass for OOP usage
- 5 telemetry tests: write/read, summary, cost estimation, dedup, total requests

### Fixed
- Config property aliases for `context_compression_threshold_tokens` and `compression_min_turns`
- 9 lint errors fixed (import sorting, trailing newlines across multiple files)

---

## [v0.4.0] — 2026-03-27

### Added — Phase 4: Context Compressor
- Context compression for long conversations via LLM summarization (`app/compressor.py`)
- `count_tokens()` function using tiktoken for model-specific token counting
- `should_compress()` convenience function for threshold checking
- `compress_context()` async function that summarizes older turns while preserving system messages and recent turns
- `X-ContextForge-No-Compress` request header to skip compression
- `X-Compressed` and `X-Compression-Ratio` response headers
- Configurable thresholds: `CONTEXT_COMPRESSION_THRESHOLD_TOKENS` (default: 2000) and `COMPRESSION_MIN_TURNS` (default: 6)
- Silent fallback to uncompressed messages on any compression error
- Compression test conversation fixtures (`tests/fixtures/compression_test_conversations.json`)
- 5 compressor tests: token counting, thresholds, fallback, system message preservation

---

## [v0.3.0] — 2025-03-25

### Added — Phase 3: Model Router
- Rule-based complexity classifier using tiktoken token counting and keyword signals
- Model tier routing: SIMPLE → gpt-3.5-turbo, COMPLEX → gpt-4o (OpenAI)
- Anthropic support: SIMPLE → claude-3-haiku, COMPLEX → claude-3-opus
- `X-ContextForge-Model-Override` request header to force a specific model
- `X-Model-Tier` and `X-Model-Selected` response headers
- Routing configuration via `config/routing_rules.yaml`
- 1000-prompt labeled benchmark dataset (`benchmarks/prompts_labeled.json`)
- OpenAI response fixture files for success and error scenarios
- 18 router tests including ≥85% accuracy validation on labeled set

### Fixed
- `get_settings()` now uses `@lru_cache` (was re-reading .env on every call)
- `VectorStore._id_map` now persisted alongside FAISS index as `.idmap` file
- `HealthResponse.version` updated from `0.1.0` to `0.3.0`
- `.env.example` now includes `OPENAI_BASE_URL`
- CI workflow now sets `OPENAI_API_KEY` env var for test execution
- Added `numpy` as explicit dependency in `requirements.txt`

---

## [v0.2.0] — 2025-03-25

### Added — Phase 2: Semantic Cache
- Embedding service using all-MiniLM-L6-v2 (loaded at startup via FastAPI lifespan)
- FAISS IndexFlatIP for cosine similarity search on normalized vectors
- Redis-backed cache store with configurable TTL (default: 24 hours)
- Semantic cache orchestrator: cache lookup → cache hit/miss → cache store
- Thread-safe FAISS index writes via `threading.Lock`
- FAISS/Redis sync handling (expired Redis entries don't cause KeyError)
- Configurable similarity threshold (default: 0.92, from `.env`)
- Cache bypass for streaming requests
- `X-Cache-Hit` response header
- 14 cache tests covering VectorStore, SemanticCache, and endpoint integration

---

## [v0.1.0] — 2025-03-25

### Added — Phase 1: Core Proxy (Passthrough)
- `POST /v1/chat/completions` endpoint with OpenAI-compatible schema
- Pydantic request/response models matching the OpenAI API spec
- Upstream forwarding to OpenAI via openai-python SDK
- Streaming SSE passthrough for `stream=True` requests
- Error propagation: upstream 4xx/5xx errors surface correctly to the caller
- `GET /health` endpoint returning `{"status":"ok","version":"..."}`
- 12 proxy tests covering health, completions, streaming, and error scenarios

---

## [v0.0.1] — 2025-03-25

### Added — Phase 0: Architecture & Repository Setup
- Repository skeleton with project structure
- `docs/ARCHITECTURE.md` — system design and component diagram
- `DECISIONS.md` — Architecture Decision Records (ADR-001 through ADR-004)
- `.env.example` with all configuration variables
- `docker-compose.yml` with app and Redis services
- `Dockerfile` for Python 3.11 slim container
- GitHub Actions CI pipeline (`ci.yml`) — ruff lint + pytest
- `CONTRIBUTING.md` — development setup and PR guidelines
- `pyproject.toml` — ruff configuration (line length 120)
- Stub files for future phases: compressor, telemetry, middleware
