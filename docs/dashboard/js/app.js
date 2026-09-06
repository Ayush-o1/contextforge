/* ============================================
   CONTEXTFORGE DASHBOARD – APP CONTROLLER
   ============================================ */

let _appData = null;
let _currentPageId = 'overview';
let _currentTimeRange = '7d';

// ─── PAGE NAVIGATION ─────────────────────────────────────────
function navigateTo(pageId) {
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.page').forEach(el => el.classList.remove('active'));

  const navItem = document.querySelector(`.nav-item[data-page="${pageId}"]`);
  if (navItem) navItem.classList.add('active');

  const page = document.getElementById(`page-${pageId}`);
  if (page) page.classList.add('active');

  const titles = {
    overview: 'Overview',
    requests: 'Request Log',
    cache: 'Cache Manager',
    router: 'Smart Router',
    telemetry: 'Telemetry',
    threshold: 'Adaptive Threshold',
  };
  const headerTitle = document.getElementById('header-title');
  if (headerTitle) headerTitle.textContent = titles[pageId] || pageId;

  _currentPageId = pageId;

  if (window.innerWidth <= 1024) {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('mobile-overlay');
    sidebar.classList.remove('mobile-open');
    overlay.classList.remove('active');
  }

  destroyAllCharts();

  if (_appData) {
    switch (pageId) {
      case 'overview': initOverviewPage(_appData); break;
      case 'requests': initRequestsPage(_appData); break;
      case 'cache': initCachePage(_appData); break;
      case 'router': initRouterPage(_appData); break;
      case 'telemetry': initTelemetryPage(_appData); break;
      case 'threshold': initThresholdPage(); break;
    }
  }
}

// ─── AGGREGATION ─────────────────────────────────────────────
// These run identically over real API records and the demo dataset in
// data.js — one code path, so the demo view can never show something the
// real dashboard couldn't also compute.

function getTimeRangeCutoff(range) {
  const spans = { '1h': 3600e3, '6h': 6 * 3600e3, '24h': 24 * 3600e3, '7d': 7 * 24 * 3600e3, '30d': 30 * 24 * 3600e3 };
  return Date.now() - (spans[range] || spans['7d']);
}

function filterByTimeRange(requests, range) {
  const cutoff = getTimeRangeCutoff(range);
  return requests.filter(r => new Date(r.timestamp).getTime() >= cutoff);
}

// Groups requests by calendar day for the trend charts. Only produces days
// that actually have data — with a fixed fetch limit, a quiet dashboard
// won't pretend to have 14 days of history it doesn't have.
function aggregateByDay(requests) {
  const byDay = new Map();
  for (const r of requests) {
    const day = (r.timestamp || '').slice(0, 10);
    if (!day) continue;
    if (!byDay.has(day)) {
      byDay.set(day, { date: day, total_requests: 0, cache_hits: 0, cache_misses: 0, _latencySum: 0, total_cost: 0 });
    }
    const bucket = byDay.get(day);
    const hit = r.cacheHit != null ? r.cacheHit : r.cache_hit;
    bucket.total_requests += 1;
    if (hit) bucket.cache_hits += 1; else bucket.cache_misses += 1;
    bucket._latencySum += r.latency != null ? r.latency : (r.latency_ms || 0);
    bucket.total_cost += r.cost != null ? r.cost : (r.estimated_cost_usd || 0);
  }
  return [...byDay.values()]
    .sort((a, b) => a.date.localeCompare(b.date))
    .map(b => ({
      date: b.date,
      total_requests: b.total_requests,
      cache_hits: b.cache_hits,
      cache_misses: b.cache_misses,
      avg_latency_ms: b.total_requests ? Math.round(b._latencySum / b.total_requests) : 0,
      total_cost: +b.total_cost.toFixed(4),
    }));
}

// Groups requests by the router's actual decision reason (see
// app/router.py's _classify) rather than an invented topic taxonomy.
function aggregateByReason(requests) {
  const byReason = new Map();
  for (const r of requests) {
    const reason = r.routing_reason || r.routingReason;
    if (!reason) continue;
    if (!byReason.has(reason)) {
      byReason.set(reason, { reason, tier: r.tier || 'unknown', count: 0, _latencySum: 0 });
    }
    const bucket = byReason.get(reason);
    bucket.count += 1;
    bucket._latencySum += r.latency != null ? r.latency : (r.latency_ms || 0);
  }
  return [...byReason.values()]
    .map(b => ({ ...b, avgLatency: Math.round(b._latencySum / b.count) }))
    .sort((a, b) => b.count - a.count);
}

function tierCounts(requests) {
  const simple = requests.filter(r => r.tier === 'simple').length;
  const complex = requests.filter(r => r.tier === 'complex').length;
  return { simple, complex };
}

function similarityScoresFromHits(requests) {
  return requests
    .filter(r => (r.cacheHit != null ? r.cacheHit : r.cache_hit))
    .map(r => r.similarity_score != null ? r.similarity_score : r.similarity)
    .filter(s => s != null);
}

// ─── PAGE INITIALIZERS ───────────────────────────────────────
function initOverviewPage(data) {
  const inRange = filterByTimeRange(data.requests, _currentTimeRange);

  _setCountUp('metric-total-requests', data.summary.total_requests, '', 0);
  _setCountUp('metric-hit-rate', data.summary.cache_hit_rate, '%', 1);
  _setCountUp('metric-avg-latency', data.summary.avg_latency_ms, 'ms', 0);
  _setCountUp('metric-total-cost', data.summary.total_cost, '', 2, '$');

  animateCardsIn('.metric-card', 80);

  initRequestsChart(aggregateByDay(inRange));
  initModelsChart(inRange);

  renderRecentRequestsTable(data.requests);
}

function initRequestsPage(data) {
  resetFilters();
  populateModelFilter(data.requests);
  renderRequestsTable(data.requests);
}

function initCachePage(data) {
  const hitScores = similarityScoresFromHits(data.requests);
  const avgSim = hitScores.length ? hitScores.reduce((a, b) => a + b, 0) / hitScores.length : 0;

  _setText('cache-total-entries', data.cacheStats.total_vectors.toLocaleString());
  _setText('cache-redis-keys', data.cacheStats.redis_keys.toLocaleString());
  _setText('cache-hit-rate', data.summary.cache_hit_rate.toFixed(1) + '%');
  _setText('cache-avg-sim', hitScores.length ? (avgSim * 100).toFixed(0) + '%' : '—');
  _setText('cache-threshold', (data.cacheStats.similarity_threshold * 100).toFixed(0) + '%');

  animateCardsIn('.metric-card', 80);

  initSimilarityChart(hitScores);
  renderCacheHitsTable(data.requests);
}

function initRouterPage(data) {
  const { simple, complex } = tierCounts(data.requests);
  const total = simple + complex;
  const complexPct = total ? (complex / total) * 100 : 0;

  _drawAccuracyRing(complexPct);
  _setText('router-total-requests', total.toLocaleString());
  _setText('router-simple-count', simple.toLocaleString());
  _setText('router-complex-count', complex.toLocaleString());

  const rCtx = document.getElementById('router-models-chart');
  if (rCtx) {
    _charts.routerModels = new Chart(rCtx, {
      type: 'doughnut',
      data: {
        labels: ['Simple', 'Complex'],
        datasets: [{ data: [simple, complex], backgroundColor: [PALETTE[3], PALETTE[5]], borderWidth: 0, hoverOffset: 6 }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '68%',
        plugins: { legend: { position: 'bottom', labels: { padding: 12 } } },
      },
    });
  }

  renderReasonTable(aggregateByReason(data.requests));
}

function initTelemetryPage(data) {
  const inRange = filterByTimeRange(data.requests, _currentTimeRange);
  const daily = aggregateByDay(inRange);
  initCostChart(daily);
  initLatencyChart(daily);
  initHitRateChart(daily);
}

function initThresholdPage() {
  loadThresholdInfo();
}

async function loadThresholdInfo() {
  const base = getApiBaseUrl();
  const headers = getApiHeaders();
  try {
    const resp = await fetch(`${base}/v1/threshold`, { headers });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    _setText('threshold-current', (data.current_threshold * 100).toFixed(1) + '%');
    _setText('threshold-baseline', (data.baseline * 100).toFixed(1) + '%');
    _setText('threshold-evaluated', data.last_evaluated_at ? timeAgo(data.last_evaluated_at) : 'Never');
  } catch {
    _setText('threshold-current', '—');
    _setText('threshold-baseline', '—');
    _setText('threshold-evaluated', 'Unavailable — backend not reachable');
  }
}

async function handleEvaluateThreshold() {
  const btn = document.getElementById('btn-evaluate-threshold');
  if (!btn) return;
  setButtonLoading(btn, 'Evaluating...');
  try {
    const base = getApiBaseUrl();
    const headers = getApiHeaders();
    const resp = await fetch(`${base}/v1/threshold/evaluate`, { method: 'POST', headers });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    setButtonSuccess(btn, 'Evaluated');
    showToast(`New threshold: ${(data.threshold * 100).toFixed(1)}% (hit rate: ${(data.cache_hit_rate * 100).toFixed(1)}%)`, 'success');
    await loadThresholdInfo();
  } catch (err) {
    resetButton(btn, 'Evaluate Now');
    showToast('Evaluation failed — is the backend running?', 'error');
    return;
  }
  setTimeout(() => resetButton(btn, 'Evaluate Now'), 1500);
}

// ─── BUTTON ACTIONS ──────────────────────────────────────────
function handleClearCache() {
  showModal('confirm-modal');
  const confirmBtn = document.getElementById('confirm-action');
  if (!confirmBtn) return;
  confirmBtn.onclick = async () => {
    hideModal('confirm-modal');
    try {
      const base = getApiBaseUrl();
      const headers = getApiHeaders();
      const resp = await fetch(`${base}/v1/cache`, { method: 'DELETE', headers });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      showToast(`Cache cleared — ${data.vectors_cleared} vectors, ${data.redis_keys_cleared} Redis keys removed`, 'success');
      await loadData();
      navigateTo(_currentPageId);
    } catch {
      showToast('Failed to clear cache — is the backend running?', 'error');
    }
  };
}

function handleExportCSV() {
  if (!_appData) return;
  const filtered = getFilteredRequests(_appData.requests);
  const headers = ['ID', 'Timestamp', 'Model', 'Tier', 'Tokens In', 'Tokens Out', 'Latency (ms)', 'Cost', 'Cache Status', 'Similarity'];
  const rows = filtered.map(r => [
    r.id, r.timestamp, r.model, r.tier || '',
    r.tokens_in, r.tokens_out, r.latency_ms,
    r.cost, r.cache_status, r.similarity_score || '',
  ]);

  const csv = [headers, ...rows].map(row => row.join(',')).join('\n');
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `contextforge-requests-${new Date().toISOString().split('T')[0]}.csv`;
  a.click();
  URL.revokeObjectURL(url);

  showToast(`Exported ${filtered.length} requests to CSV`, 'success');
}

function handleTimeRange(range) {
  _currentTimeRange = range;
  document.querySelectorAll('.time-range-btn').forEach(b => b.classList.remove('active'));
  const btn = document.querySelector(`.time-range-btn[data-range="${range}"]`);
  if (btn) btn.classList.add('active');
  if (_appData && (_currentPageId === 'overview' || _currentPageId === 'telemetry')) {
    navigateTo(_currentPageId);
  }
}

// ─── API NORMALIZATION ───────────────────────────────────────
// API: http://localhost:8000/health, /v1/telemetry, /v1/telemetry/summary, /v1/cache/stats
function _normalizeApiRecord(r) {
  return {
    id: r.request_id, request_id: r.request_id, timestamp: r.timestamp,
    model: r.model_used || r.model_requested, model_used: r.model_used,
    tokens_in: r.prompt_tokens || 0, tokens_out: r.completion_tokens || 0,
    latency_ms: r.latency_ms || 0, cost: r.estimated_cost_usd || 0,
    cache_status: r.cache_hit ? 'HIT' : 'MISS', cache_hit: !!r.cache_hit,
    similarity_score: r.similarity_score, compressed: r.compressed || false,
    compression_ratio: r.compression_ratio || 1.0,
    tier: r.tier || null, routing_reason: r.routing_reason || null,
  };
}
function _normalizeApiSummary(s) {
  return {
    total_requests: s.total_requests || 0,
    cache_hit_rate: s.cache_hit_rate != null ? +(s.cache_hit_rate * 100).toFixed(1) : 0,
    avg_latency_ms: s.avg_latency_ms || 0,
    total_cost: s.total_cost_usd || 0,
    cache_hits: s.cache_hits || 0,
  };
}

// ─── DATA LOADING ────────────────────────────────────────────
async function loadData() {
  let connected = false;

  try {
    connected = await checkAPIConnection();
  } catch {
    connected = false;
  }

  updateConnectionStatus(connected);

  if (connected) {
    try {
      const base = getApiBaseUrl();
      const headers = getApiHeaders();
      const [summaryRes, requestsRes, cacheRes] = await Promise.all([
        fetch(`${base}/v1/telemetry/summary`, { headers }),
        fetch(`${base}/v1/telemetry?limit=500`, { headers }),
        fetch(`${base}/v1/cache/stats`, { headers }),
      ]);
      if (!summaryRes.ok || !requestsRes.ok || !cacheRes.ok) throw new Error('API request failed');
      const summary = await summaryRes.json();
      const requests = await requestsRes.json();
      const cacheData = await cacheRes.json();

      _appData = {
        summary: _normalizeApiSummary(summary),
        requests: (requests.records || []).map(_normalizeApiRecord),
        cacheStats: cacheData,
      };
    } catch {
      updateConnectionStatus(false);
      _useMockData();
    }
  } else {
    _useMockData();
  }
}

function _useMockData() {
  _appData = {
    summary: MOCK_SUMMARY,
    requests: MOCK_REQUESTS,
    cacheStats: MOCK_CACHE_STATS,
  };
}

// ─── HELPERS ─────────────────────────────────────────────────
function _setCountUp(id, value, suffix, decimals, prefix) {
  const el = document.getElementById(id);
  if (!el) return;
  if (prefix) {
    const span = el;
    animateCountUp({
      set textContent(v) { span.textContent = prefix + v; }
    }, value, suffix, decimals);
    return;
  }
  animateCountUp(el, value, suffix, decimals);
}

function _setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

function _drawAccuracyRing(pct) {
  const circle = document.getElementById('accuracy-ring-fill');
  const label = document.getElementById('accuracy-ring-label');
  if (!circle) return;

  const radius = 54;
  const circumference = 2 * Math.PI * radius;
  circle.style.strokeDasharray = circumference;
  circle.style.strokeDashoffset = circumference;
  requestAnimationFrame(() => {
    circle.style.strokeDashoffset = circumference - (pct / 100) * circumference;
  });

  if (label) label.textContent = pct.toFixed(0) + '%';
}

// ─── LIVE REFRESH ────────────────────────────────────────────
let _liveRefreshEnabled = false;
let _liveRefreshInterval = null;
const REFRESH_INTERVAL_MS = 10000;

function toggleLiveRefresh() {
  _liveRefreshEnabled = !_liveRefreshEnabled;
  const btn = document.getElementById('live-refresh-btn');
  if (btn) btn.classList.toggle('active', _liveRefreshEnabled);

  if (_liveRefreshEnabled) {
    showToast('Live refresh enabled (10s)', 'success', 2000);
    _liveRefreshInterval = setInterval(async () => {
      await loadData();
      if (_appData && _currentPageId) navigateTo(_currentPageId);
    }, REFRESH_INTERVAL_MS);
  } else {
    showToast('Live refresh disabled', 'info', 2000);
    if (_liveRefreshInterval) {
      clearInterval(_liveRefreshInterval);
      _liveRefreshInterval = null;
    }
  }
}

// ─── DYNAMIC API BASE URL ────────────────────────────────────
function getApiBaseUrl() {
  // When served by FastAPI at /dashboard, use relative URLs
  // When opened standalone, default to localhost:8000
  if (window.location.pathname.startsWith('/dashboard')) {
    return window.location.origin;
  }
  return 'http://localhost:8000';
}

// ─── API AUTH HEADERS ─────────────────────────────────────────
// Only needed if the backend has CONTEXTFORGE_API_KEYS set (auth is off by
// default). Set a token once via the browser console:
//   localStorage.setItem('contextforge_api_key', 'your-token')
function getApiHeaders() {
  let token = null;
  try {
    token = localStorage.getItem('contextforge_api_key');
  } catch {
    token = null;
  }
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// ─── EVENT DELEGATION ────────────────────────────────────────
function _bindEvents() {
  document.querySelectorAll('.nav-item[data-page]').forEach(item => {
    item.addEventListener('click', () => navigateTo(item.dataset.page));
  });

  document.querySelectorAll('[data-action="toggle-sidebar"]').forEach(btn => {
    btn.addEventListener('click', toggleSidebar);
  });

  document.querySelectorAll('.time-range-btn[data-range]').forEach(btn => {
    btn.addEventListener('click', () => handleTimeRange(btn.dataset.range));
  });

  document.addEventListener('click', e => {
    const actionEl = e.target.closest('[data-action]');
    if (!actionEl) return;
    const action = actionEl.dataset.action;

    switch (action) {
      case 'export-csv': handleExportCSV(); break;
      case 'clear-cache': handleClearCache(); break;
      case 'evaluate-threshold': handleEvaluateThreshold(); break;
      case 'toggle-live-refresh': toggleLiveRefresh(); break;
      case 'close-modal': hideModal(actionEl.closest('.modal-overlay')?.id); break;
      case 'cancel-modal': hideModal(actionEl.closest('.modal-overlay')?.id); break;
    }
  });

  const filterSearch = document.getElementById('req-search');
  const filterModel = document.getElementById('filter-model');
  const filterStatus = document.getElementById('filter-status');
  const filterTier = document.getElementById('tier-filter');

  if (filterSearch) {
    filterSearch.addEventListener('input', e => {
      _searchTerm = e.target.value;
      _currentPage = 1;
      renderRequestsTable(_appData.requests);
    });
  }
  if (filterModel) {
    filterModel.addEventListener('change', e => {
      _filterModel = e.target.value;
      _currentPage = 1;
      renderRequestsTable(_appData.requests);
    });
  }
  if (filterStatus) {
    filterStatus.addEventListener('change', e => {
      _filterStatus = e.target.value;
      _currentPage = 1;
      renderRequestsTable(_appData.requests);
    });
  }
  if (filterTier) {
    filterTier.addEventListener('change', e => {
      _filterTier = e.target.value;
      _currentPage = 1;
      renderRequestsTable(_appData.requests);
    });
  }

  const prevBtn = document.getElementById('prev-page');
  const nextBtn = document.getElementById('next-page');
  if (prevBtn) prevBtn.addEventListener('click', () => prevPage(_appData.requests));
  if (nextBtn) nextBtn.addEventListener('click', () => nextPage(_appData.requests));
}

// ─── BOOT / INIT ─────────────────────────────────────────────
async function init() {
  initSidebar();
  _bindEvents();

  await loadData();

  navigateTo('overview');

  setTimeout(hideBoot, 400);
}

document.addEventListener('DOMContentLoaded', init);
