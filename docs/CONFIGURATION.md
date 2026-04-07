# ContextForge Configuration Reference

> Complete reference for all environment variables.

---

## Setup

Copy the example file and fill in your values:

```bash
cp .env.example .env
```

All variables are loaded by `app/config.py` using [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/). They are validated at startup — if a required variable is missing, the server will fail to start with a clear error message.

---

## LLM Provider Keys

| Variable | Description | Default | Required |
|----------|-------------|---------|:--------:|
| `OPENAI_API_KEY` | OpenAI API key | — | Only for OpenAI |
| `ANTHROPIC_API_KEY` | Anthropic API key | `""` | Only for Anthropic |
| `GEMINI_API_KEY` | Google Gemini API key | `""` | Only for Gemini |
| `GROQ_API_KEY` | Groq API key | `""` | Only for Groq |
| `MISTRAL_API_KEY` | Mistral API key | `""` | Only for Mistral |
| `PREFERRED_PROVIDER` | Default provider: `openai`, `anthropic`, `gemini`, `groq`, `mistral`, `ollama` | `openai` | No |
| `OPENAI_BASE_URL` | Override OpenAI API base URL (for proxies or testing) | `https://api.openai.com/v1` | No |

> **LiteLLM routing:** You can specify any LiteLLM-prefixed model name in requests, e.g., `groq/llama3-8b-8192`, `gemini/gemini-1.5-pro`, `mistral/mistral-small`. ContextForge passes these through LiteLLM automatically.

## Model Routing

| Variable | Description | Default |
|----------|-------------|---------|
| `SIMPLE_MODEL` | Model used for simple/cheap prompts | `gpt-3.5-turbo` |
| `COMPLEX_MODEL` | Model used for complex/expensive prompts | `gpt-4o` |

You can set these to any LiteLLM-compatible model string, e.g.,:
- `SIMPLE_MODEL=groq/llama3-8b-8192`
- `COMPLEX_MODEL=gemini/gemini-1.5-pro`

---

## Semantic Cache

| Variable | Description | Default |
|----------|-------------|---------|
| `SIMILARITY_THRESHOLD` | Cosine similarity threshold for cache hits (0.0–1.0). Higher = stricter matching. | `0.92` |
| `CACHE_TTL_SECONDS` | How long cached responses are stored in Redis (in seconds) | `86400` (24 hours) |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379` |

---

## Context Compression

| Variable | Description | Default |
|----------|-------------|---------|
| `CONTEXT_COMPRESSION_THRESHOLD_TOKENS` | Token count above which compression activates | `2000` |
| `COMPRESSION_MIN_TURNS` | Minimum conversation turns before compression triggers | `6` |

Compression only activates when **both** conditions are met. If either is below the threshold, compression is skipped.

---

## Adaptive Threshold

| Variable | Description | Default |
|----------|-------------|---------|
| `ADAPTIVE_THRESHOLD_ENABLED` | Enable adaptive similarity threshold auto-tuning | `true` |
| `ADAPTIVE_THRESHOLD_WINDOW` | Number of recent requests to analyze for hit rate | `100` |
| `ADAPTIVE_THRESHOLD_MIN` | Minimum allowed similarity threshold | `0.70` |
| `ADAPTIVE_THRESHOLD_MAX` | Maximum allowed similarity threshold | `0.98` |

When enabled, the system automatically adjusts the similarity threshold based on cache hit rates:
- Hit rate > 60% → threshold raised by 0.01 (stricter matching)
- Hit rate < 20% → threshold lowered by 0.01 (looser matching)
- Otherwise → no change

---

## Storage Paths

| Variable | Description | Default |
|----------|-------------|---------|
| `SQLITE_DB_PATH` | Path for the telemetry SQLite database | `./data/telemetry.db` |
| `FAISS_INDEX_PATH` | Path for the FAISS vector index file | `./data/faiss.index` |

The FAISS index has a companion file at `<FAISS_INDEX_PATH>.idmap` that stores the mapping between index positions and cache keys. Both files must be kept together.

---

## Logging

| Variable | Description | Default |
|----------|-------------|---------|
| `LOG_LEVEL` | Logging verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR` | `INFO` |

Logs are structured JSON via [structlog](https://www.structlog.org/).

---

## Example `.env` File

```bash
# LLM Provider Keys (set only the ones you use)
OPENAI_API_KEY=sk-your-key-here
ANTHROPIC_API_KEY=
GEMINI_API_KEY=
GROQ_API_KEY=
MISTRAL_API_KEY=
PREFERRED_PROVIDER=openai

# Model Routing
SIMPLE_MODEL=gpt-3.5-turbo
COMPLEX_MODEL=gpt-4o

# Cache
REDIS_URL=redis://localhost:6379
SIMILARITY_THRESHOLD=0.92
CACHE_TTL_SECONDS=86400

# Compression
CONTEXT_COMPRESSION_THRESHOLD_TOKENS=2000
COMPRESSION_MIN_TURNS=6

# Adaptive Threshold
ADAPTIVE_THRESHOLD_ENABLED=true
ADAPTIVE_THRESHOLD_WINDOW=100
ADAPTIVE_THRESHOLD_MIN=0.70
ADAPTIVE_THRESHOLD_MAX=0.98

# Storage
SQLITE_DB_PATH=./data/telemetry.db
FAISS_INDEX_PATH=./data/faiss.index

# Logging
LOG_LEVEL=INFO
```
