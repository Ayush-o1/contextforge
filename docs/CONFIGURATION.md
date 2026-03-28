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
| `OPENAI_API_KEY` | Your OpenAI API key | — | ✅ |
| `ANTHROPIC_API_KEY` | Your Anthropic API key | `""` | No |
| `PREFERRED_PROVIDER` | Which provider to use: `openai` or `anthropic` | `openai` | No |
| `OPENAI_BASE_URL` | Override OpenAI API base URL (for proxies or testing) | `https://api.openai.com/v1` | No |

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
# LLM Provider Keys
OPENAI_API_KEY=sk-your-key-here
ANTHROPIC_API_KEY=
PREFERRED_PROVIDER=openai

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
