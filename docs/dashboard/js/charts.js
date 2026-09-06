/* ============================================
   CONTEXTFORGE DASHBOARD – CHART.JS CHARTS
   ============================================ */

// Store references so we can destroy on page change
const _charts = {};

// ─── GLOBAL DEFAULTS ─────────────────────────────────────────
function _applyDefaults() {
  Chart.defaults.color = '#a1a1a1';
  Chart.defaults.borderColor = 'rgba(255,255,255,0.06)';
  Chart.defaults.font.family = "'Inter', -apple-system, BlinkMacSystemFont, sans-serif";
  Chart.defaults.font.size = 11;
  Chart.defaults.plugins.legend.labels.boxWidth = 10;
  Chart.defaults.plugins.legend.labels.boxHeight = 10;
  Chart.defaults.plugins.legend.labels.padding = 16;
  Chart.defaults.plugins.legend.labels.useBorderRadius = true;
  Chart.defaults.plugins.legend.labels.borderRadius = 2;
  Chart.defaults.animation = { duration: 800, easing: 'easeOutQuart' };
  Chart.defaults.plugins.tooltip.backgroundColor = 'rgba(17,17,17,0.95)';
  Chart.defaults.plugins.tooltip.titleColor = '#ededed';
  Chart.defaults.plugins.tooltip.bodyColor = '#a1a1a1';
  Chart.defaults.plugins.tooltip.borderColor = 'rgba(255,255,255,0.1)';
  Chart.defaults.plugins.tooltip.borderWidth = 1;
  Chart.defaults.plugins.tooltip.cornerRadius = 8;
  Chart.defaults.plugins.tooltip.padding = 10;
  Chart.defaults.plugins.tooltip.displayColors = true;
  Chart.defaults.plugins.tooltip.boxPadding = 4;
}

const PALETTE = [
  '#3b82f6', '#8b5cf6', '#06b6d4', '#22c55e',
  '#f59e0b', '#ef4444', '#ec4899', '#f97316'
];

// ─── REQUESTS OVER TIME (bar) ────────────────────────────────
function initRequestsChart(data) {
  _applyDefaults();
  const ctx = document.getElementById('chart-requests');
  if (!ctx) return;

  _charts.requests = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: data.map(d => d.date.slice(5)),
      datasets: [
        {
          label: 'Cache Hits',
          data: data.map(d => d.cache_hits),
          backgroundColor: 'rgba(34,197,94,0.7)',
          borderRadius: 4,
          borderSkipped: false,
          barPercentage: 0.7,
          categoryPercentage: 0.8,
        },
        {
          label: 'Cache Misses',
          data: data.map(d => d.cache_misses),
          backgroundColor: 'rgba(59,130,246,0.7)',
          borderRadius: 4,
          borderSkipped: false,
          barPercentage: 0.7,
          categoryPercentage: 0.8,
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { position: 'top', align: 'end' },
      },
      scales: {
        x: {
          stacked: true,
          grid: { display: false },
          ticks: { maxRotation: 0 },
        },
        y: {
          stacked: true,
          grid: { color: 'rgba(255,255,255,0.04)' },
          ticks: { precision: 0 },
        }
      }
    }
  });
}

// ─── MODELS DISTRIBUTION (doughnut) ──────────────────────────
function initModelsChart(data) {
  _applyDefaults();
  const ctx = document.getElementById('chart-models');
  if (!ctx) return;

  // Count by model
  const counts = {};
  data.forEach(r => { counts[r.model] = (counts[r.model] || 0) + 1; });
  const labels = Object.keys(counts);
  const values = Object.values(counts);

  _charts.models = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: PALETTE.slice(0, labels.length),
        borderWidth: 0,
        hoverOffset: 6,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '68%',
      plugins: {
        legend: {
          position: 'right',
          labels: { padding: 12 },
        },
      },
    }
  });
}

// ─── SIMILARITY DISTRIBUTION (histogram-like bar) ────────────
// `scores` is a plain array of similarity_score values (0-1) taken from
// recent cache-hit requests — real numbers, not a per-entry cache dump
// (the backend never exposes cached prompt text, so there's no "cache
// entries" list to show — see docs/dashboard/README notes in the Cache page).
function initSimilarityChart(scores) {
  _applyDefaults();
  const ctx = document.getElementById('chart-similarity');
  if (!ctx) return;

  // Bucketize
  const buckets = { '0.70-0.80': 0, '0.80-0.90': 0, '0.90-0.94': 0, '0.94-0.97': 0, '0.97-1.00': 0 };
  scores.forEach(s => {
    if (s < 0.80) buckets['0.70-0.80']++;
    else if (s < 0.90) buckets['0.80-0.90']++;
    else if (s < 0.94) buckets['0.90-0.94']++;
    else if (s < 0.97) buckets['0.94-0.97']++;
    else buckets['0.97-1.00']++;
  });

  _charts.similarity = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: Object.keys(buckets),
      datasets: [{
        label: 'Entries',
        data: Object.values(buckets),
        backgroundColor: 'rgba(139,92,246,0.7)',
        borderRadius: 6,
        borderSkipped: false,
        barPercentage: 0.6,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false } },
        y: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { precision: 0 } },
      }
    }
  });
}

// ─── LATENCY OVER TIME (line) ────────────────────────────────
function initLatencyChart(data) {
  _applyDefaults();
  const ctx = document.getElementById('chart-latency');
  if (!ctx) return;

  _charts.latency = new Chart(ctx, {
    type: 'line',
    data: {
      labels: data.map(d => d.date.slice(5)),
      datasets: [{
        label: 'Avg Latency (ms)',
        data: data.map(d => d.avg_latency_ms),
        borderColor: '#f59e0b',
        backgroundColor: 'rgba(245,158,11,0.08)',
        borderWidth: 2,
        pointRadius: 3,
        pointBackgroundColor: '#f59e0b',
        pointBorderWidth: 0,
        pointHoverRadius: 6,
        fill: true,
        tension: 0.35,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false }, ticks: { maxRotation: 0 } },
        y: {
          grid: { color: 'rgba(255,255,255,0.04)' },
          ticks: { callback: v => v + 'ms' },
        }
      }
    }
  });
}

// ─── COST OVER TIME (line + area) ────────────────────────────
function initCostChart(data) {
  _applyDefaults();
  const ctx = document.getElementById('chart-cost');
  if (!ctx) return;

  _charts.cost = new Chart(ctx, {
    type: 'line',
    data: {
      labels: data.map(d => d.date.slice(5)),
      datasets: [{
        label: 'Daily Cost ($)',
        data: data.map(d => d.total_cost),
        borderColor: '#3b82f6',
        backgroundColor: 'rgba(59,130,246,0.08)',
        borderWidth: 2,
        pointRadius: 3,
        pointBackgroundColor: '#3b82f6',
        pointBorderWidth: 0,
        pointHoverRadius: 6,
        fill: true,
        tension: 0.35,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false }, ticks: { maxRotation: 0 } },
        y: {
          grid: { color: 'rgba(255,255,255,0.04)' },
          ticks: { callback: v => '$' + v },
        }
      }
    }
  });
}

// ─── HIT RATE OVER TIME (line) ───────────────────────────────
function initHitRateChart(data) {
  _applyDefaults();
  const ctx = document.getElementById('chart-hitrate');
  if (!ctx) return;

  const hitRates = data.map(d => +((d.cache_hits / d.total_requests) * 100).toFixed(1));

  _charts.hitrate = new Chart(ctx, {
    type: 'line',
    data: {
      labels: data.map(d => d.date.slice(5)),
      datasets: [{
        label: 'Hit Rate (%)',
        data: hitRates,
        borderColor: '#22c55e',
        backgroundColor: 'rgba(34,197,94,0.08)',
        borderWidth: 2,
        pointRadius: 3,
        pointBackgroundColor: '#22c55e',
        pointBorderWidth: 0,
        pointHoverRadius: 6,
        fill: true,
        tension: 0.35,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false }, ticks: { maxRotation: 0 } },
        y: {
          grid: { color: 'rgba(255,255,255,0.04)' },
          ticks: { callback: v => v + '%' },
          min: 0,
          max: 100,
        }
      }
    }
  });
}

// ─── DESTROY ALL CHARTS ──────────────────────────────────────
function destroyAllCharts() {
  Object.values(_charts).forEach(c => {
    if (c && typeof c.destroy === 'function') c.destroy();
  });
  Object.keys(_charts).forEach(k => delete _charts[k]);
}
