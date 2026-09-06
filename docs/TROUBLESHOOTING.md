# Troubleshooting

> Solutions for common issues when running ContextForge locally.

---

## Server Won't Start

### `OPENAI_API_KEY` validation error

```
pydantic_settings.errors.SettingsError: ...OPENAI_API_KEY...
```

**Fix:** Copy `.env.example` to `.env` and add your OpenAI API key:

```bash
cp .env.example .env
# Edit .env and set OPENAI_API_KEY=sk-your-key-here
```

### Port 8000 already in use

```
ERROR: [Errno 48] Address already in use
```

**Fix:** Kill the existing process or use a different port:

```bash
# Find and kill the process
lsof -ti:8000 | xargs kill -9

# Or use a different port
uvicorn app.main:app --port 8001
```

### Module not found errors

```
ModuleNotFoundError: No module named 'fastapi'
```

**Fix:** Make sure your virtual environment is activated and dependencies are installed:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Redis Issues

### Connection refused

```
redis.exceptions.ConnectionError: Error connecting to localhost:6379
```

**Fix:** Start Redis:

```bash
docker run -d --name contextforge-redis -p 6379:6379 redis:7-alpine
```

> **Note:** The server still starts without Redis, and chat completions still succeed — `SemanticCache.lookup()`/`.store()` catch Redis errors and degrade to a cache miss (see `app/cache.py`) rather than failing the request. `GET /health` reports this via its `redis` field (`"ok"` / `"unreachable"` / `"unknown"`) without failing the liveness check itself. Cache-management endpoints (`/v1/cache/stats`, `DELETE /v1/cache`) similarly return partial results (0 Redis keys) instead of crashing.

### Redis container exists but stopped

```bash
docker start contextforge-redis
```

---

## Cache Issues

### FAISS index and ID map out of sync

If cache lookups return wrong results or errors, the FAISS index and its companion `.idmap` file may be out of sync.

**Fix:** Delete both files and restart:

```bash
rm data/faiss.index data/faiss.index.idmap
# Restart the server — a fresh index will be created
```

### Cache hit rate too low or too high

The adaptive threshold may need manual evaluation:

```bash
# Check current threshold
curl http://localhost:8000/v1/threshold

# Trigger evaluation
curl -X POST http://localhost:8000/v1/threshold/evaluate

# Or flush the cache entirely
curl -X DELETE http://localhost:8000/v1/cache
```

---

## Dashboard Issues

### Dashboard shows "Using Mock Data"

The backend is not reachable at `http://localhost:8000`. Start the server:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Dashboard shows 0 for all metrics

This is normal if no requests have been made through the proxy yet. Send a test request:

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d '{"model":"gpt-3.5-turbo","messages":[{"role":"user","content":"Hello"}]}'
```

Then refresh the dashboard.

### Charts not rendering

Ensure Chart.js is loading from CDN. If you're behind a firewall, the CDN (`cdn.jsdelivr.net`) may be blocked. Check the browser console for network errors.

---

## Test Issues

### `PYTHONPATH` error

```
ModuleNotFoundError: No module named 'app'
```

**Fix:** Set `PYTHONPATH` when running tests:

```bash
PYTHONPATH=. pytest tests/ -v
```

### Embedding model download hangs

On first run, `sentence-transformers` downloads the `all-MiniLM-L6-v2` model (~80 MB). This requires internet access. If it hangs:

1. Check your internet connection
2. Check if `~/.cache/torch/` is writable
3. Try: `python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"`

If the model is already cached but startup still pauses for ~10–20s on a `HEAD` request to huggingface.co (e.g. no internet, or behind a firewall), set `HF_HUB_OFFLINE=1` to skip the remote check entirely and load straight from cache.

### `Fatal Python error: Aborted` when running tests on macOS (Apple Silicon)

```
Fatal Python error: Aborted
...
File ".../site-packages/torch/__init__.py", line 496 in <module>
File ".../site-packages/sentence_transformers/...
```

This is a known conflict between `faiss-cpu` and `torch` on macOS: both bundle their own OpenMP runtime, and loading both in the same process aborts hard instead of raising a catchable Python exception. It's a local dev-environment issue on macOS specifically — the Linux-based CI and Docker images are unaffected.

**Fix:** set before running tests or the server locally:

```bash
export KMP_DUPLICATE_LIB_OK=TRUE
```

This is intentionally **not** set inside application code — it silences a real (if usually harmless, for this workload) OpenMP duplicate-runtime warning, so it should be an explicit choice made by whoever runs the process, not a default baked into `app/`.

### Running the live E2E suite (`tests/test_e2e.py`)

Excluded by default (`pytest tests/` deselects anything marked `e2e` — see `pyproject.toml`). To run it intentionally against a real provider:

```bash
RUN_E2E_TESTS=1 OPENAI_API_KEY=sk-your-real-key PYTHONPATH=. pytest tests/test_e2e.py -m e2e -v
```

Requires Redis running and will make real, billed API calls (kept minimal — see the module docstring in `tests/test_e2e.py`).

---

## Docker Issues

### `docker compose up` fails with build errors

**Fix:** Make sure Docker is running and you have the `.env` file:

```bash
cp .env.example .env
docker compose up --build -d
```

### Container starts but `/health` returns connection refused

The app may still be loading the embedding model. Wait 10–15 seconds, then retry:

```bash
sleep 15 && curl http://localhost:8000/health
```

---

## SQLite / Telemetry Issues

### Database locked

```
sqlite3.OperationalError: database is locked
```

This can happen if multiple processes write to telemetry simultaneously. ContextForge uses WAL mode to minimize this, but it can still occur.

**Fix:** Restart the server. Do not delete the `-wal` or `-shm` companion files while the server is running.

### Telemetry data missing

Telemetry is stored at the path set by `SQLITE_DB_PATH` (default: `./data/telemetry.db`). If you changed this in `.env`, check the correct path. The `data/` directory is created automatically on first write.

---

## Still Stuck?

- Check the [GitHub Issues](https://github.com/Ayush-o1/contextforge/issues) for known problems
- Open a new issue with your error message, OS, and Python version
- Contact the maintainer: ayushh.ofc10@gmail.com
