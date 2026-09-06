/* ============================================
   CONTEXTFORGE DASHBOARD – TABLE RENDERING
   ============================================ */

// ─── HTML ESCAPING ───────────────────────────────────────────
// model/tier/routing_reason ultimately come from request data the *caller*
// controls (the chat completions body, and — for model_used — the
// X-ContextForge-Model-Override header), not from the dashboard's own
// state. Every dynamic value gets escaped before going into innerHTML so a
// request like {"model": "<img src=x onerror=alert(1)>"} shows up as inert
// text in the log instead of running in whoever's viewing the dashboard.
function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, ch => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[ch]));
}

// ─── PAGINATION STATE ────────────────────────────────────────
let _currentPage = 1;
const _pageSize = 10;
let _searchTerm = '';
let _filterModel = '';
let _filterStatus = '';
let _filterTier = '';

// ─── FILTER ──────────────────────────────────────────────────
function getFilteredRequests(requests) {
  return requests.filter(r => {
    const rid = r.id || r.request_id || '';
    const rmodel = r.model || r.model_used || '';
    const cacheHit = r.cacheHit != null ? r.cacheHit : r.cache_hit;
    const cacheStatus = r.cache_status || (cacheHit ? 'HIT' : 'MISS');
    if (_searchTerm) {
      const q = _searchTerm.toLowerCase();
      const match = rid.toLowerCase().includes(q) || rmodel.toLowerCase().includes(q);
      if (!match) return false;
    }
    if (_filterModel && rmodel !== _filterModel) return false;
    if (_filterStatus && cacheStatus !== _filterStatus) return false;
    if (_filterTier && r.tier !== _filterTier) return false;
    return true;
  });
}

// ─── REQUESTS TABLE ──────────────────────────────────────────
function renderRequestsTable(requests) {
  const filtered = getFilteredRequests(requests);
  const totalPages = Math.max(1, Math.ceil(filtered.length / _pageSize));
  if (_currentPage > totalPages) _currentPage = totalPages;

  const start = (_currentPage - 1) * _pageSize;
  const pageItems = filtered.slice(start, start + _pageSize);

  const tbody = document.getElementById('req-tbody');
  if (!tbody) return;

  if (pageItems.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:32px;color:var(--text-tertiary)">No requests match your filters</td></tr>`;
  } else {
    tbody.innerHTML = pageItems.map(r => {
      const rid = r.id || r.request_id || '';
      const rmodel = r.model || r.model_used || '';
      const lat = r.latency != null ? r.latency : (r.latency_ms || 0);
      const rcost = r.cost != null ? r.cost : (r.estimated_cost_usd || 0);
      const cacheHit = r.cacheHit != null ? r.cacheHit : r.cache_hit;
      const cacheStatus = r.cache_status || (cacheHit ? 'HIT' : 'MISS');
      const tIn = r.tokens_in || r.prompt_tokens || 0;
      const tOut = r.tokens_out || r.completion_tokens || 0;
      const sim = r.similarity_score != null ? r.similarity_score : (r.similarity || null);
      const latencyClass = lat < 500 ? 'latency-fast' : lat < 1500 ? 'latency-medium' : 'latency-slow';
      const pillClass = cacheHit ? 'hit' : 'miss';
      const simText = sim !== null && sim !== undefined ? (sim * 100).toFixed(0) + '%' : '—';
      const tier = r.tier ? escapeHtml(r.tier) : '—';

      return `<tr>
        <td>
          <span class="mono">${escapeHtml(rid.slice(0, 12))}</span>
          <button class="copy-btn" onclick="copyToClipboard('${escapeHtml(rid)}', this)" title="Copy ID">⧉</button>
        </td>
        <td>${timeAgo(r.timestamp)}</td>
        <td>${escapeHtml(rmodel)}</td>
        <td class="text-muted">${tier}</td>
        <td>${tIn.toLocaleString()} / ${tOut.toLocaleString()}</td>
        <td class="${latencyClass}">${formatLatency(lat)}</td>
        <td>${formatCost(rcost)}</td>
        <td><span class="pill ${pillClass}">${cacheStatus}</span> ${simText !== '—' ? `<span class="text-muted" style="font-size:0.7rem;margin-left:4px">${simText}</span>` : ''}</td>
      </tr>`;
    }).join('');
  }

  const info = document.getElementById('page-info');
  if (info) {
    const end = Math.min(start + _pageSize, filtered.length);
    info.textContent = filtered.length === 0
      ? 'No results'
      : `${start + 1}–${end} of ${filtered.length}`;
  }

  const prevBtn = document.getElementById('prev-page');
  const nextBtn = document.getElementById('next-page');
  if (prevBtn) prevBtn.disabled = _currentPage <= 1;
  if (nextBtn) nextBtn.disabled = _currentPage >= totalPages;
}

// ─── PAGINATION CONTROLS ─────────────────────────────────────
function prevPage(requests) {
  if (_currentPage > 1) {
    _currentPage--;
    renderRequestsTable(requests);
  }
}

function nextPage(requests) {
  const filtered = getFilteredRequests(requests);
  const totalPages = Math.ceil(filtered.length / _pageSize);
  if (_currentPage < totalPages) {
    _currentPage++;
    renderRequestsTable(requests);
  }
}

function resetFilters() {
  _searchTerm = '';
  _filterModel = '';
  _filterStatus = '';
  _filterTier = '';
  _currentPage = 1;
  const searchEl = document.getElementById('req-search');
  const modelEl = document.getElementById('filter-model');
  const statusEl = document.getElementById('filter-status');
  const tierEl = document.getElementById('tier-filter');
  if (searchEl) searchEl.value = '';
  if (modelEl) modelEl.value = '';
  if (statusEl) statusEl.value = '';
  if (tierEl) tierEl.value = '';
}

// Populates the model filter from whatever models actually appear in the
// data, instead of a hardcoded guess list that drifts from what's really
// configured (see PREFERRED_PROVIDER / SIMPLE_MODEL / COMPLEX_MODEL).
function populateModelFilter(requests) {
  const select = document.getElementById('filter-model');
  if (!select) return;
  const models = [...new Set(requests.map(r => r.model || r.model_used).filter(Boolean))].sort();
  const current = select.value;
  select.innerHTML = '<option value="">All Models</option>' +
    models.map(m => `<option value="${escapeHtml(m)}">${escapeHtml(m)}</option>`).join('');
  if (models.includes(current)) select.value = current;
}

// ─── CACHE PAGE: RECENT HITS ─────────────────────────────────
// The backend stores cached responses in Redis keyed by a content hash and
// vectors in FAISS — never the original prompt text — so there's no
// "cache entries" list with prompt previews to show honestly. This shows
// the real per-request data that *is* available: which recent requests
// were served from cache, and at what similarity.
function renderCacheHitsTable(requests) {
  const tbody = document.getElementById('cache-tbody');
  if (!tbody) return;

  const hits = requests.filter(r => (r.cacheHit != null ? r.cacheHit : r.cache_hit)).slice(0, 15);

  if (hits.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:32px;color:var(--text-tertiary)">No cache hits in the current window</td></tr>`;
    return;
  }

  tbody.innerHTML = hits.map(r => {
    const rid = r.id || r.request_id || '';
    const rmodel = r.model || r.model_used || '';
    const sim = r.similarity_score != null ? r.similarity_score : r.similarity;
    const simText = sim != null ? (sim * 100).toFixed(1) + '%' : '—';
    return `<tr>
      <td class="mono">${escapeHtml(rid.slice(0, 12))}</td>
      <td>${escapeHtml(rmodel)}</td>
      <td>${simText}</td>
      <td>${timeAgo(r.timestamp)}</td>
      <td>${formatCost(r.cost != null ? r.cost : (r.estimated_cost_usd || 0))} saved</td>
    </tr>`;
  }).join('');
}

// ─── ROUTER PAGE: TIER BREAKDOWN ─────────────────────────────
// `rows` come from aggregateByReason() in app.js — real counts grouped by
// the router's actual decision reason (e.g. "token_count:150<=200",
// "complex_keyword:analyze"), not a fabricated topic taxonomy the router
// has no way of actually knowing.
function renderReasonTable(rows) {
  const tbody = document.getElementById('router-tbody');
  if (!tbody) return;

  if (rows.length === 0) {
    tbody.innerHTML = `<tr><td colspan="4" style="text-align:center;padding:32px;color:var(--text-tertiary)">No requests yet</td></tr>`;
    return;
  }

  tbody.innerHTML = rows.map(row => {
    const tierClass = row.tier === 'complex' ? 'pill miss' : 'pill hit';
    return `<tr>
      <td class="mono">${escapeHtml(row.reason)}</td>
      <td><span class="${tierClass}">${escapeHtml(row.tier)}</span></td>
      <td>${row.count.toLocaleString()}</td>
      <td>${formatLatency(row.avgLatency)}</td>
    </tr>`;
  }).join('');
}

// ─── RECENT REQUESTS (overview) ──────────────────────────────
function renderRecentRequestsTable(requests) {
  const tbody = document.getElementById('recent-tbody');
  if (!tbody) return;

  const recent = requests.slice(0, 5);
  tbody.innerHTML = recent.map(r => {
    const rid = r.id || r.request_id || '';
    const rmodel = r.model || r.model_used || '';
    const lat = r.latency != null ? r.latency : (r.latency_ms || 0);
    const rcost = r.cost != null ? r.cost : (r.estimated_cost_usd || 0);
    const cacheHit = r.cacheHit != null ? r.cacheHit : r.cache_hit;
    const cacheStatus = r.cache_status || (cacheHit ? 'HIT' : 'MISS');
    const latencyClass = lat < 500 ? 'latency-fast' : lat < 1500 ? 'latency-medium' : 'latency-slow';
    const pillClass = cacheHit ? 'hit' : 'miss';

    return `<tr>
      <td class="mono">${escapeHtml(rid.slice(0, 12))}</td>
      <td>${timeAgo(r.timestamp)}</td>
      <td>${escapeHtml(rmodel)}</td>
      <td class="${latencyClass}">${formatLatency(lat)}</td>
      <td>${formatCost(rcost)}</td>
      <td><span class="pill ${pillClass}">${cacheStatus}</span></td>
    </tr>`;
  }).join('');
}
