# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/).

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
