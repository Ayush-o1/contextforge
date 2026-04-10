# ContextForge Configuration Reference

> Complete reference for all environment variables supported by ContextForge.

---

## Setup

Copy the example file and fill in your values:

```bash
cp .env.example .env
```

All variables are loaded by `app/config.py` using [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/). They are validated at startup — if a required variable is missing or invalid, the server will fail with a clear error message.

---

## LLM Provider Keys

| Variable | Description | Default | Required |
|----------|-------------|---------|:--------:|
| `OPENAI_API_KEY` | OpenAI API key | `""` | Only for OpenAI |
| `ANTHROPIC_API_KEY` | Anthropic Claude API key | `""` | Only for Anthropic |
| `GEMINI_API_KEY` | Google Gemini API key | `""` | Only for Gemini |
| `GROQ_API_KEY` | Groq API key | `""` | Only for Groq |
| `MISTRAL_API_KEY` | Mistral AI API key | `""` | Only for Mistral |
| `COHERE_API_KEY` | Cohere API key | `""` | Only for Cohere |
| `XAI_API_KEY` | xAI (Grok) API key | `""` | Only for xAI |
| `OLLAMA_BASE_URL` | Ollama server base URL | `http://localhost:11434` | Only for Ollama |
| `OPENAI_BASE_URL` | Override OpenAI API base URL (for proxies or testing) | `https://api.openai.com/v1` | No |

> **At least one provider key is required.** You can configure as many providers as you like — only those with API keys set will be recognized by the routing layer.

> **LiteLLM routing:** Specify any LiteLLM-prefixed model name in requests to route through alternate providers, e.g., `groq/llama3-8b-8192`, `gemini/gemini-1.5-pro`, `mistral/mistral-small`. ContextForge passes these through LiteLLM automatically.

---

## Model Routing

| Variable | Description | Default |
|----------|-------------|---------|
| `PREFERRED_PROVIDER` | Default provider: `openai`, `anthropic`, `gemini`, `groq`, `mistral`, `ollama` | `openai` |
| `SIMPLE_MODEL` | Model used for simple/cheap prompts | `gpt-3.5-turbo` |
| `COMPLEX_MODEL` | Model used for complex/expensive prompts | `gpt-4o` |

Both `SIMPLE_MODEL` and `COMPLEX_MODEL` support provider-prefixed LiteLLM model names:

```bash
SIMPLE_MODEL=groq/llama3-8b-8192
COMPLEX_MODEL=gemini/gemini-1.5-pro
```

---

## Semantic Cache

| Variable | Description | Default |
|----------|-------------|---------|
| `SIMILARITY_THRESHOLD` | Cosine similarity threshold for cache hits (0.0–1.0). Higher = stricter matching. | `0.92` |
| `CACHE_TTL_SECONDS` | How long cached responses are stored in Redis (seconds) | `86400` (24 hours) |
| `REDIS_URL` | Redis connection string used by the semantic cache | `redis://localhost:6379` |

---

## Redis (LiteLLM Built-in Cache)

These variables configure the optional LiteLLM response cache (exact-match, complements the FAISS semantic cache):

| Variable | Description | Default |
|----------|-------------|---------|
| `ENABLE_CACHE` | Enable LiteLLM's built-in Redis response cache | `false` |
| `REDIS_HOST` | Redis host for LiteLLM cache | `localhost` |
| `REDIS_PORT` | Redis port for LiteLLM cache | `6379` |
| `REDIS_PASSWORD` | Redis password (leave blank if none) | `""` |

---

## Context Compression

Compression only activates when **both** conditions are met simultaneously. If either condition is below its threshold, compression is skipped.

| Variable | Description | Default |
|----------|-------------|---------|
| `COMPRESS_THRESHOLD` | Total token count above which compression is considered | `2000` |
| `COMPRESS_MIN_TURNS` | Minimum number of non-system messages before compression triggers | `6` |
| `COMPRESS_KEEP_RECENT` | Number of most-recent non-system turns to keep verbatim | `4` |
| `COMPRESS_SUMMARY_MODEL` | Model used to generate conversation summaries | `gpt-3.5-turbo` |

> **Tip:** Set `COMPRESS_SUMMARY_MODEL=groq/llama3-8b-8192` to use a fast, free model for summarization instead of OpenAI.

> **Skip compression per-request:** Set the `X-ContextForge-No-Compress: true` request header to bypass compression for a single request.

---

## Adaptive Threshold

When enabled, the system automatically adjusts the similarity threshold based on observed cache hit rates:

| Variable | Description | Default |
|----------|-------------|---------|
| `ADAPTIVE_THRESHOLD_ENABLED` | Enable adaptive similarity threshold auto-tuning | `true` |
| `ADAPTIVE_THRESHOLD_WINDOW` | Number of recent requests to analyze for hit rate | `100` |
| `ADAPTIVE_THRESHOLD_MIN` | Minimum allowed similarity threshold | `0.70` |
| `ADAPTIVE_THRESHOLD_MAX` | Maximum allowed similarity threshold | `0.98` |

**Tuning logic (applied at each evaluation):**
- Hit rate > 60% → threshold raised by 0.01 (stricter matching)
- Hit rate < 20% → threshold lowered by 0.01 (looser matching)
- Otherwise → no change

---

## Storage Paths

| Variable | Description | Default |
|----------|-------------|---------|
| `SQLITE_DB_PATH` | Path for the telemetry SQLite database | `./data/telemetry.db` |
| `FAISS_INDEX_PATH` | Path for the FAISS vector index file | `./data/faiss.index` |

> The FAISS index has a companion file at `<FAISS_INDEX_PATH>.idmap` that stores the mapping between index positions and cache keys. Both files must always be kept together.

---

## Logging

| Variable | Description | Default |
|----------|-------------|---------|
| `LOG_LEVEL` | Logging verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR` | `INFO` |

Logs are structured JSON via [structlog](https://www.structlog.org/).

---

## Test Mode

| Variable | Description | Default |
|----------|-------------|---------|
| `TEST_MODE` | Force all requests to use the cheapest available model (useful for development) | `false` |

---

## OpenTelemetry (Optional)

OpenTelemetry tracing is opt-in. The SDK is always installed; tracing is a no-op when `ENABLE_OTEL=false`.

| Variable | Description | Default |
|----------|-------------|---------|
| `ENABLE_OTEL` | Enable OpenTelemetry distributed tracing | `false` |
| `OTEL_ENDPOINT` | OTLP gRPC collector endpoint (e.g., Jaeger, Grafana Tempo) | `http://localhost:4317` |

---

## Example `.env` File

```bash
# ─── LLM Provider Keys (set only the ones you use) ─────────────────────────
OPENAI_API_KEY=sk-your-key-here
ANTHROPIC_API_KEY=
GEMINI_API_KEY=
GROQ_API_KEY=
MISTRAL_API_KEY=
COHERE_API_KEY=
XAI_API_KEY=

# Ollama (local models) — default: http://localhost:11434
OLLAMA_BASE_URL=http://localhost:11434

# ─── Model Routing ──────────────────────────────────────────────────────────
PREFERRED_PROVIDER=openai
SIMPLE_MODEL=gpt-3.5-turbo
COMPLEX_MODEL=gpt-4o

# ─── Semantic Cache ─────────────────────────────────────────────────────────
REDIS_URL=redis://localhost:6379
SIMILARITY_THRESHOLD=0.92
CACHE_TTL_SECONDS=86400

# ─── LiteLLM Built-in Cache (optional — set ENABLE_CACHE=true to activate) ──
ENABLE_CACHE=false
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=

# ─── Context Compression ────────────────────────────────────────────────────
COMPRESS_THRESHOLD=2000
COMPRESS_MIN_TURNS=6
COMPRESS_KEEP_RECENT=4
COMPRESS_SUMMARY_MODEL=gpt-3.5-turbo

# ─── Adaptive Threshold ─────────────────────────────────────────────────────
ADAPTIVE_THRESHOLD_ENABLED=true
ADAPTIVE_THRESHOLD_WINDOW=100
ADAPTIVE_THRESHOLD_MIN=0.70
ADAPTIVE_THRESHOLD_MAX=0.98

# ─── Storage ────────────────────────────────────────────────────────────────
SQLITE_DB_PATH=./data/telemetry.db
FAISS_INDEX_PATH=./data/faiss.index

# ─── Logging ────────────────────────────────────────────────────────────────
LOG_LEVEL=INFO

# ─── OpenAI Base URL (for custom endpoints / local proxies) ─────────────────
OPENAI_BASE_URL=https://api.openai.com/v1

# ─── Test Mode ──────────────────────────────────────────────────────────────
TEST_MODE=false

# ─── OpenTelemetry (opt-in) ─────────────────────────────────────────────────
ENABLE_OTEL=false
OTEL_ENDPOINT=http://localhost:4317
```
