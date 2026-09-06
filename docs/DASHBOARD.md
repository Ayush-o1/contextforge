# ContextForge Dashboard

> Local monitoring dashboard for the ContextForge LLM proxy.

---

## Overview

The dashboard is a standalone static web app at `docs/dashboard/`. It reads real telemetry from the running backend — request log, cache stats, routing decisions, the adaptive threshold — and renders it with Chart.js. If the backend isn't reachable, it falls back to a small demo dataset and says so plainly ("Using Demo Data" badge); it never silently shows fake numbers next to real ones.

---

## How to Open

**Option A — via the running backend (recommended):**

```
http://localhost:8000/dashboard/
```

**Option B — open the file directly:**

```
docs/dashboard/index.html
```

Either way it auto-detects the backend at `GET /health`. If auth is enabled (`CONTEXTFORGE_API_KEYS` set), give it a token first: open the browser console and run
`localStorage.setItem('contextforge_api_key', 'your-token')`.

---

## Pages

| Page | What It Shows |
|------|--------------|
| **Overview** | Metric cards (total requests, cache hit rate, avg latency, total cost), requests-over-time chart, model distribution doughnut, recent requests table |
| **Requests** | Full request log — search, model/cache-status/tier filters, pagination, CSV export |
| **Cache** | Real cache stats (FAISS vector count, Redis key count, active threshold), similarity-score distribution of recent hits, recent cache-hit table |
| **Router** | Simple/complex tier split, routing-reason breakdown (why the classifier picked each tier) |
| **Telemetry** | Daily cost, latency, and cache-hit-rate trends |
| **Threshold** | Current adaptive threshold vs. the static baseline, manual "Evaluate Now" trigger |

The old "Settings" page (API URL / max tokens / TTL fields with a Save button that didn't persist anywhere) was removed — it didn't correspond to anything the backend could actually do. The "Threshold" page replaced it with something real: `GET /v1/threshold` and `POST /v1/threshold/evaluate` actually exist and actually do something.

There's also no "cache entries" browser with prompt previews — the backend stores response hashes and FAISS vectors, never the original prompt text, so there's genuinely nothing to list per-entry. The Cache page shows what's real instead: aggregate stats plus which recent requests were served from cache.

---

## Backend API Endpoints

| Endpoint | Used For |
|----------|----------|
| `GET /health` | Connection detection |
| `GET /v1/telemetry?limit=500` | Request records — tables and all trend charts are computed from this client-side |
| `GET /v1/telemetry/summary` | Overview metric cards |
| `GET /v1/cache/stats` | Cache page stats |
| `GET /v1/threshold` | Threshold page |
| `POST /v1/threshold/evaluate` | "Evaluate Now" button |
| `DELETE /v1/cache` | "Clear Cache" button |

If `CONTEXTFORGE_API_KEYS` is set on the backend, every one of these except `/health` needs an `Authorization: Bearer <token>` header — see `getApiHeaders()` in `app.js`.

---

## Architecture

Vanilla HTML, CSS, and JavaScript — no build step, no framework.

```
docs/dashboard/
├── index.html          # Shell: sidebar, header, all page sections
├── css/
│   └── style.css       # Dark theme, component styles
└── js/
    ├── data.js         # Demo dataset, used only when the backend is unreachable
    ├── ui.js            # Toast, modal, sidebar, formatters, clipboard
    ├── charts.js        # Chart.js chart initialization
    ├── tables.js        # HTML escaping, table rendering, pagination, filters
    └── app.js           # Navigation, data loading + aggregation, button handlers
```

### Data flow

```
init() → checkAPIConnection() (GET /health)
  → connected:    fetch summary + telemetry(limit=500) + cache stats
  → disconnected: use the demo dataset in data.js
  → normalize records to a common shape (_normalizeApiRecord)
  → navigateTo('overview') → aggregate + render
```

The important part: **real and demo data go through the exact same aggregation functions** — `aggregateByDay()`, `aggregateByReason()`, `tierCounts()`, `similarityScoresFromHits()` in `app.js`. There's one code path for "turn a list of requests into charts and tables," not a separate hand-tuned mock chart and a separate real one that can drift apart.

### Why there's no live "router accuracy"

Routing *accuracy* needs a ground-truth label ("was `complex` the right call for this prompt?"), and production traffic doesn't come with one. The only accuracy number that exists is measured offline, against the labeled 1,000-prompt set in `benchmarks/prompts_labeled.json` (see `benchmarks/run_benchmark.py`, ~88% last run). The Router page shows the real, live tier split and routing reasons instead of inventing a live "accuracy" the system has no way to know.

### Security note

Every dynamic value rendered into a table (`model`, `tier`, `routing_reason`, request IDs) goes through `escapeHtml()` in `tables.js` before it touches `innerHTML`. `model_used` in particular can be fully attacker-controlled — a client can set it via the `X-ContextForge-Model-Override` header, which the backend does not sanitize (see `app/router.py`) — so an unescaped render here was a real stored-XSS path into the dashboard. Don't reintroduce raw interpolation into `innerHTML` for these fields.

---

## Element IDs

| ID | Element |
|----|---------|
| `req-tbody` | Request log table body |
| `cache-tbody` | Recent cache hits table body |
| `router-tbody` | Routing reasons table body |
| `recent-tbody` | Recent requests table body (overview) |
| `chart-requests` | Requests over time canvas |
| `chart-models` | Model distribution canvas |
| `chart-similarity` | Similarity distribution canvas |
| `chart-latency` | Latency trend canvas |
| `chart-cost` | Cost trend canvas |
| `chart-hitrate` | Hit rate trend canvas |
| `router-models-chart` | Simple/complex tier split canvas |
| `clear-cache-btn` | Clear cache button |
| `btn-evaluate-threshold` | Threshold page's evaluate button |
| `req-search` | Request search input |
| `filter-model` | Model filter select (populated dynamically) |
| `filter-status` | Cache status filter select |
| `tier-filter` | Tier filter select |
| `export-btn` | Export CSV button |
| `conn-badge` | Connection status badge |
| `sidebar-toggle` | Sidebar collapse button |
| `toast-container` | Toast notification container |

---

## Development

No build step — edit files in `docs/dashboard/` and refresh the browser.

**Adding a page:** section in `index.html` (`id="page-yourpage"`) + nav item (`data-page="yourpage"`) + a case in `navigateTo()` + an `initYourPage(data)` function in `app.js`.

**Adding a chart:** `<canvas id="chart-yourname">` + an `initYourNameChart()` function in `charts.js`, registered in the `_charts` object so `destroyAllCharts()` cleans it up on page change.
