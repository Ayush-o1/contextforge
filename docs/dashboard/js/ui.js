/* ============================================
   CONTEXTFORGE DASHBOARD – UI UTILITIES
   ============================================ */

// ─── TOAST ───────────────────────────────────────────────────
function showToast(message, type = 'success', duration = 3000) {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;

  const icons = { success: '✓', error: '✕', warning: '⚠', info: 'ℹ' };
  toast.innerHTML = `
    <span class="toast-icon">${icons[type] || icons.info}</span>
    <span>${message}</span>
  `;

  toast.addEventListener('click', () => dismissToast(toast));
  container.appendChild(toast);

  setTimeout(() => dismissToast(toast), duration);
  return toast;
}

function dismissToast(toastEl) {
  if (!toastEl || toastEl.classList.contains('removing')) return;
  toastEl.classList.add('removing');
  setTimeout(() => toastEl.remove(), 280);
}

// ─── MODAL ───────────────────────────────────────────────────
function showModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.classList.add('active');
}

function hideModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.classList.remove('active');
}

// ─── SIDEBAR ─────────────────────────────────────────────────
function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('mobile-overlay');

  if (window.innerWidth <= 1024) {
    sidebar.classList.toggle('mobile-open');
    overlay.classList.toggle('active');
  } else {
    sidebar.classList.toggle('collapsed');
  }
}

function initSidebar() {
  const overlay = document.getElementById('mobile-overlay');
  if (overlay) {
    overlay.addEventListener('click', () => {
      const sidebar = document.getElementById('sidebar');
      sidebar.classList.remove('mobile-open');
      overlay.classList.remove('active');
    });
  }
}

// ─── COUNT-UP ANIMATION ──────────────────────────────────────
function animateCountUp(element, targetValue, suffix = '', decimals = 0, duration = 1200) {
  const start = 0;
  const startTime = performance.now();

  function step(currentTime) {
    const elapsed = currentTime - startTime;
    const progress = Math.min(elapsed / duration, 1);
    // ease-out cubic
    const ease = 1 - Math.pow(1 - progress, 3);
    const current = start + (targetValue - start) * ease;

    element.textContent = current.toFixed(decimals).replace(/\B(?=(\d{3})+(?!\d))/g, ',') + suffix;

    if (progress < 1) {
      requestAnimationFrame(step);
    }
  }
  requestAnimationFrame(step);
}

function initCountUps() {
  document.querySelectorAll('[data-countup]').forEach(el => {
    const target = parseFloat(el.dataset.countup);
    const suffix = el.dataset.suffix || '';
    const decimals = parseInt(el.dataset.decimals || '0', 10);
    animateCountUp(el, target, suffix, decimals);
  });
}

// ─── CARD ENTRANCE ANIMATION ─────────────────────────────────
function animateCardsIn(selector, delay = 60) {
  const cards = document.querySelectorAll(selector);
  cards.forEach((card, i) => {
    setTimeout(() => card.classList.add('visible'), i * delay);
  });
}

// ─── CLIPBOARD ───────────────────────────────────────────────
function copyToClipboard(text, buttonEl) {
  navigator.clipboard.writeText(text).then(() => {
    if (buttonEl) {
      const orig = buttonEl.textContent;
      buttonEl.textContent = '✓';
      buttonEl.style.color = 'var(--success)';
      setTimeout(() => {
        buttonEl.textContent = orig;
        buttonEl.style.color = '';
      }, 1500);
    }
    showToast('Copied to clipboard', 'success', 2000);
  }).catch(() => {
    showToast('Failed to copy', 'error', 2000);
  });
}

// ─── BUTTON STATES ───────────────────────────────────────────
function setButtonLoading(buttonEl, text = 'Loading...') {
  buttonEl._originalHTML = buttonEl.innerHTML;
  buttonEl.classList.add('loading');
  buttonEl.innerHTML = `<span class="btn-spinner"></span> ${text}`;
}

function setButtonSuccess(buttonEl, text) {
  buttonEl.classList.remove('loading');
  buttonEl.innerHTML = `✓ ${text}`;
  buttonEl.style.background = 'var(--success)';
  buttonEl.style.color = '#fff';
}

function resetButton(buttonEl, originalText) {
  buttonEl.classList.remove('loading');
  if (buttonEl._originalHTML) {
    buttonEl.innerHTML = buttonEl._originalHTML;
  } else {
    buttonEl.textContent = originalText;
  }
  buttonEl.style.background = '';
  buttonEl.style.color = '';
}

// ─── API CONNECTION CHECK ────────────────────────────────────
async function checkAPIConnection() {
  try {
    const base = typeof getApiBaseUrl === 'function' ? getApiBaseUrl() : 'http://localhost:8000';
    const resp = await fetch(`${base}/health`, { signal: AbortSignal.timeout(3000) });
    return resp.ok;
  } catch {
    return false;
  }
}

function updateConnectionStatus(connected) {
  const badge = document.getElementById('conn-badge');
  if (!badge) return;
  if (connected) {
    badge.classList.add('connected');
    badge.querySelector('.connection-label').textContent = 'API Connected';
  } else {
    badge.classList.remove('connected');
    badge.querySelector('.connection-label').textContent = 'Using Mock Data';
  }
}

// ─── BOOT SCREEN ─────────────────────────────────────────────
function hideBoot() {
  const boot = document.getElementById('boot-screen');
  if (boot) boot.classList.add('hidden');
}

// ─── FORMATTERS ──────────────────────────────────────────────
function timeAgo(isoString) {
  const now = Date.now();
  const then = new Date(isoString).getTime();
  const diff = now - then;

  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function formatCost(cost) {
  if (cost < 0.01) return `$${cost.toFixed(4)}`;
  if (cost < 1) return `$${cost.toFixed(3)}`;
  return `$${cost.toFixed(2)}`;
}

function formatLatency(ms) {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}
