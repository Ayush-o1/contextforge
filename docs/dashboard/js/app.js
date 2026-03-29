/* ============================================
   CONTEXTFORGE DASHBOARD – APP CONTROLLER
   ============================================ */

let _appData = null;
let _currentPageId = 'overview';

// ─── PAGE NAVIGATION ─────────────────────────────────────────
function navigateTo(pageId) {
  // Remove active from all nav items and pages
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.page').forEach(el => el.classList.remove('active'));

  // Set active
  const navItem = document.querySelector(`.nav-item[data-page="${pageId}"]`);
  if (navItem) navItem.classList.add('active');

  const page = document.getElementById(`page-${pageId}`);
  if (page) page.classList.add('active');

  // Update header title
  const titles = {
    overview: 'Overview',
    requests: 'Request Log',
    cache: 'Cache Manager',
    router: 'Smart Router',
    telemetry: 'Telemetry',
    settings: 'Settings',
  };
  const headerTitle = document.getElementById('header-title');
  if (headerTitle) headerTitle.textContent = titles[pageId] || pageId;

  _currentPageId = pageId;

  // Close mobile sidebar
  if (window.innerWidth <= 1024) {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('mobile-overlay');
    sidebar.classList.remove('mobile-open');
    overlay.classList.remove('active');
  }

  // Destroy old charts and reinit page
  destroyAllCharts();

  if (_appData) {
    switch (pageId) {
      case 'overview': initOverviewPage(_appData); break;
      case 'requests': initRequestsPage(_appData); break;
      case 'cache': initCachePage(_appData); break;
      case 'router': initRouterPage(_appData); break;
      case 'telemetry': initTelemetryPage(_appData); break;
      case 'settings': initSettingsPage(); break;
    }
  }
}

// ─── PAGE INITIALIZERS ───────────────────────────────────────
function initOverviewPage(data) {
  // Metric cards
  _setCountUp('metric-total-requests', data.summary.total_requests, '', 0);
  _setCountUp('metric-hit-rate', data.summary.cache_hit_rate, '%', 1);
  _setCountUp('metric-avg-latency', data.summary.avg_latency_ms, 'ms', 0);
  _setCountUp('metric-total-cost', data.summary.total_cost, '', 2, '$');

  animateCardsIn('.metric-card', 80);

  // Charts
  initRequestsChart(data.dailyStats);
  initModelsChart(data.requests);

  // Recent table
  renderRecentRequestsTable(data.requests);
}

function initRequestsPage(data) {
  resetFilters();
  renderRequestsTable(data.requests);
}

function initCachePage(data) {
  // Stats
  _setText('cache-total-entries', data.cacheStats.total_entries.toLocaleString());
  _setText('cache-memory', `${data.cacheStats.memory_used_mb} / ${data.cacheStats.memory_limit_mb} MB`);
  _setText('cache-hit-rate', data.cacheStats.hit_rate + '%');
  _setText('cache-avg-sim', (data.cacheStats.avg_similarity * 100).toFixed(0) + '%');

  animateCardsIn('.metric-card', 80);

  // Similarity chart
  initSimilarityChart(data.cacheEntries);

  // Table
  renderCacheTable(data.cacheEntries);
}

function initRouterPage(data) {
  // Accuracy ring
  const totalRequests = data.routerCategories.reduce((s, c) => s + c.requests, 0);
  const weightedAcc = data.routerCategories.reduce((s, c) => s + c.accuracy * c.requests, 0) / totalRequests;
  _drawAccuracyRing(weightedAcc);

  _setText('router-total-requests', totalRequests.toLocaleString());
  _setText('router-avg-accuracy', weightedAcc.toFixed(1) + '%');
  _setText('router-categories', data.routerCategories.length.toString());

  // Models chart for router
  const routerModelCounts = {};
  data.routerCategories.forEach(c => {
    routerModelCounts[c.model_assigned] = (routerModelCounts[c.model_assigned] || 0) + c.requests;
  });

  const rCtx = document.getElementById('router-models-chart');
  if (rCtx) {
    const labels = Object.keys(routerModelCounts);
    const vals = Object.values(routerModelCounts);
    _charts.routerModels = new Chart(rCtx, {
      type: 'doughnut',
      data: {
        labels,
        datasets: [{ data: vals, backgroundColor: PALETTE.slice(0, labels.length), borderWidth: 0, hoverOffset: 6 }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '68%',
        plugins: { legend: { position: 'bottom', labels: { padding: 12 } } },
      }
    });
  }

  renderRouterTable(data.routerCategories);
}

function initTelemetryPage(data) {
  initCostChart(data.dailyStats);
  initLatencyChart(data.dailyStats);
  initHitRateChart(data.dailyStats);
}

function initSettingsPage() {
  // Populate settings with defaults
  const fields = {
    'setting-api-url': 'http://localhost:8000',
    'setting-cache-ttl': '3600',
    'setting-similarity': '0.92',
    'setting-max-tokens': '4096',
  };
  Object.entries(fields).forEach(([id, val]) => {
    const el = document.getElementById(id);
    if (el && !el.value) el.value = val;
  });
}

// ─── BUTTON ACTIONS ──────────────────────────────────────────
function handleClearCache() {
  showModal('confirm-modal');
  const confirmBtn = document.getElementById('confirm-action');
  if (confirmBtn) {
    confirmBtn.onclick = () => {
      hideModal('confirm-modal');
      showToast('Cache cleared successfully', 'success');
    };
  }
}

function handleSimulateRequest() {
  const btn = document.getElementById('simulate-btn');
  if (!btn) return;

  setButtonLoading(btn, 'Simulating...');

  setTimeout(() => {
    setButtonSuccess(btn, 'Request Sent');

    // Add a fake request
    if (_appData) {
      const newReq = {
        id: 'req_' + Math.random().toString(36).slice(2, 10),
        timestamp: new Date().toISOString(),
        model: ['gpt-4o', 'claude-3.5-sonnet', 'gemini-1.5-pro'][Math.floor(Math.random() * 3)],
        endpoint: '/v1/chat/completions',
        tokens_in: 500 + Math.floor(Math.random() * 1500),
        tokens_out: 100 + Math.floor(Math.random() * 500),
        latency_ms: 200 + Math.floor(Math.random() * 2000),
        cost: +(0.001 + Math.random() * 0.06).toFixed(4),
        cache_status: Math.random() > 0.5 ? 'HIT' : 'MISS',
        similarity_score: Math.random() > 0.5 ? +(0.88 + Math.random() * 0.12).toFixed(2) : null,
        status: 200,
      };
      _appData.requests.unshift(newReq);
      showToast(`Simulated ${newReq.model} request (${newReq.cache_status})`, 'info');
    }

    setTimeout(() => resetButton(btn, 'Simulate Request'), 1500);
  }, 1200);
}

function handleExportCSV() {
  if (!_appData) return;
  const filtered = getFilteredRequests(_appData.requests);
  const headers = ['ID', 'Timestamp', 'Model', 'Endpoint', 'Tokens In', 'Tokens Out', 'Latency (ms)', 'Cost', 'Cache Status', 'Similarity'];
  const rows = filtered.map(r => [
    r.id, r.timestamp, r.model, r.endpoint,
    r.tokens_in, r.tokens_out, r.latency_ms,
    r.cost, r.cache_status, r.similarity_score || ''
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

function handleSaveSettings() {
  const btn = document.getElementById('btn-save-settings');
  if (!btn) return;

  setButtonLoading(btn, 'Saving...');
  setTimeout(() => {
    setButtonSuccess(btn, 'Saved');
    showToast('Settings saved successfully', 'success');
    setTimeout(() => resetButton(btn, 'Save Settings'), 1500);
  }, 800);
}

function handleResetSettings() {
  document.getElementById('setting-api-url').value = 'http://localhost:8000';
  document.getElementById('setting-cache-ttl').value = '3600';
  document.getElementById('setting-similarity').value = '0.92';
  document.getElementById('setting-max-tokens').value = '4096';
  showToast('Settings reset to defaults', 'info');
}

function handleTimeRange(range) {
  document.querySelectorAll('.time-range-btn').forEach(b => b.classList.remove('active'));
  const btn = document.querySelector(`.time-range-btn[data-range="${range}"]`);
  if (btn) btn.classList.add('active');
  showToast(`Time range set to ${range}`, 'info', 1500);
}

// ─── API NORMALIZATION ───────────────────────────────────────
// API: http://localhost:8000/health, /v1/telemetry, /v1/telemetry/summary, /v1/cache/stats
function _normalizeApiRecord(r) {
  return {
    id: r.request_id, request_id: r.request_id, timestamp: r.timestamp,
    model: r.model_used || r.model_requested, model_used: r.model_used,
    endpoint: '/v1/chat/completions',
    tokens_in: r.prompt_tokens || 0, tokens_out: r.completion_tokens || 0,
    latency_ms: r.latency_ms || 0, cost: r.estimated_cost_usd || 0,
    cache_status: r.cache_hit ? 'HIT' : 'MISS', cache_hit: !!r.cache_hit,
    similarity_score: r.similarity_score, compressed: r.compressed || false,
    compression_ratio: r.compression_ratio || 1.0, status: 200,
  };
}
function _normalizeApiSummary(s) {
  return {
    total_requests: s.total_requests || 0,
    cache_hit_rate: s.cache_hit_rate != null ? +(s.cache_hit_rate * 100).toFixed(1) : 0,
    avg_latency_ms: s.avg_latency_ms || 0,
    total_cost: s.total_cost_usd || 0,
    cache_hits: s.cache_hits || 0,
    total_tokens: 0, requests_today: 0, cost_today: 0,
  };
}
function normalizeRequest(r) {
  return {
    id: r.request_id,
    timestamp: r.timestamp,
    model: r.model_used,
    cacheHit: r.cache_hit,
    latency: r.latency_ms,
    cost: r.estimated_cost_usd,
    tokens: (r.prompt_tokens || 0) + (r.completion_tokens || 0),
    tier: (r.prompt_tokens || 0) > 100 ? 'complex' : 'simple',
    similarity: r.similarity_score || 0,
    compressed: !!r.compressed
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
      const [summaryRes, requestsRes, cacheRes] = await Promise.all([
        fetch(`${base}/v1/telemetry/summary`),
        fetch(`${base}/v1/telemetry?limit=50`),
        fetch(`${base}/v1/cache/stats`),
      ]);
      const summary = await summaryRes.json();
      const requests = await requestsRes.json();
      const cacheData = await cacheRes.json();

      _appData = {
        summary: _normalizeApiSummary(summary),
        requests: (requests.records || []).map(r => { r._normalized = normalizeRequest(r); return _normalizeApiRecord(r); }),
        cacheStats: Object.assign({}, MOCK_CACHE_STATS, cacheData),
        cacheEntries: MOCK_CACHE_ENTRIES,
        dailyStats: MOCK_DAILY_STATS,
        routerCategories: MOCK_ROUTER_CATEGORIES,
      };
    } catch {
      // Fall back gracefully
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
    cacheEntries: MOCK_CACHE_ENTRIES,
    dailyStats: MOCK_DAILY_STATS,
    routerCategories: MOCK_ROUTER_CATEGORIES,
  };
}

// ─── HELPERS ─────────────────────────────────────────────────
function _setCountUp(id, value, suffix, decimals, prefix) {
  const el = document.getElementById(id);
  if (!el) return;
  if (prefix) {
    // For cost – animate the number then prepend prefix
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
  // Animate from empty to value
  circle.style.strokeDashoffset = circumference;
  requestAnimationFrame(() => {
    circle.style.strokeDashoffset = circumference - (pct / 100) * circumference;
  });

  if (label) label.textContent = pct.toFixed(1) + '%';
}

// ─── LIVE REFRESH ────────────────────────────────────────────
let _liveRefreshEnabled = false;
let _liveRefreshInterval = null;
const REFRESH_INTERVAL_MS = 10000; // 10 seconds

function toggleLiveRefresh() {
  _liveRefreshEnabled = !_liveRefreshEnabled;
  const btn = document.getElementById('live-refresh-btn');
  if (btn) {
    btn.classList.toggle('active', _liveRefreshEnabled);
  }

  if (_liveRefreshEnabled) {
    showToast('Live refresh enabled (10s)', 'success', 2000);
    _liveRefreshInterval = setInterval(async () => {
      await loadData();
      if (_appData && _currentPageId) {
        navigateTo(_currentPageId);
      }
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

// ─── EVENT DELEGATION ────────────────────────────────────────
function _bindEvents() {
  // Nav clicks
  document.querySelectorAll('.nav-item[data-page]').forEach(item => {
    item.addEventListener('click', () => navigateTo(item.dataset.page));
  });

  // Sidebar toggle
  document.querySelectorAll('[data-action="toggle-sidebar"]').forEach(btn => {
    btn.addEventListener('click', toggleSidebar);
  });

  // Time range
  document.querySelectorAll('.time-range-btn[data-range]').forEach(btn => {
    btn.addEventListener('click', () => handleTimeRange(btn.dataset.range));
  });

  // Buttons by data-action
  document.addEventListener('click', e => {
    const actionEl = e.target.closest('[data-action]');
    if (!actionEl) return;
    const action = actionEl.dataset.action;

    switch (action) {
      case 'simulate': handleSimulateRequest(); break;
      case 'export-csv': handleExportCSV(); break;
      case 'clear-cache': handleClearCache(); break;
      case 'save-settings': handleSaveSettings(); break;
      case 'reset-settings': handleResetSettings(); break;
      case 'toggle-live-refresh': toggleLiveRefresh(); break;
      case 'close-modal': hideModal(actionEl.closest('.modal-overlay')?.id); break;
      case 'cancel-modal': hideModal(actionEl.closest('.modal-overlay')?.id); break;
    }
  });

  // Filter inputs
  const filterSearch = document.getElementById('req-search');
  const filterModel = document.getElementById('filter-model');
  const filterStatus = document.getElementById('filter-status');

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

  // Pagination
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

  // Hide boot after a brief delay for smooth transition
  setTimeout(hideBoot, 400);
}

// Start
document.addEventListener('DOMContentLoaded', init);

