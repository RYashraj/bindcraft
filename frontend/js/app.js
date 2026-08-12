/**
 * app.js — BindCraft SPA Router & Global State
 * Handles routing, API helpers, toasts, and system status.
 */

// ── Global State ──────────────────────────────────────────────────────────────
window.BC = {
  currentPage: null,
  currentProject: null,
  currentJob: null,
  systemStatus: null,
};

// ── API Base ──────────────────────────────────────────────────────────────────
const API = '/api';

async function apiFetch(path, opts = {}) {
  try {
    const res = await fetch(API + path, {
      headers: { 'Content-Type': 'application/json', ...opts.headers },
      ...opts,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    if (res.status === 204) return null;
    return await res.json();
  } catch (e) {
    if (!(e instanceof TypeError)) throw e; // network error
    throw new Error('Cannot reach BindCraft server. Is it running?');
  }
}

window.API = {
  get:    (path)        => apiFetch(path),
  post:   (path, body)  => apiFetch(path, { method: 'POST', body: JSON.stringify(body) }),
  put:    (path, body)  => apiFetch(path, { method: 'PUT',  body: JSON.stringify(body) }),
  delete: (path)        => apiFetch(path, { method: 'DELETE' }),
  upload: (path, form)  => fetch(API + path, { method: 'POST', body: form }).then(async r => {
    if (!r.ok) {
      const e = await r.json().catch(() => ({ detail: r.statusText }));
      throw new Error(e.detail || `Upload failed (${r.status})`);
    }
    return r.json();
  }),
};

// ── Router ────────────────────────────────────────────────────────────────────
const PAGES = {
  dashboard:   renderDashboard,
  'new-project': renderNewProject,
  wizard:      renderWizard,
  review:      renderReview,
  results:     renderResults,
};

function navigate(page, params = {}) {
  BC.currentPage = page;
  Object.assign(BC, params);
  const main = document.getElementById('main-content');
  main.innerHTML = '';

  const fn = PAGES[page];
  if (!fn) {
    main.innerHTML = `<div class="container page"><h2>Page not found: ${page}</h2></div>`;
    return;
  }

  updateBreadcrumb(page, params);
  fn(main, params);
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

window.navigate = navigate;

function updateBreadcrumb(page, params) {
  const bar = document.getElementById('breadcrumb-bar');
  const bc  = document.getElementById('breadcrumb');

  const crumbs = [
    { label: 'Dashboard', page: 'dashboard' },
  ];

  if (page === 'new-project') {
    crumbs.push({ label: 'New Project' });
  } else if (page === 'wizard' && BC.currentProject) {
    crumbs.push({ label: BC.currentProject.name || 'Project', page: 'new-project', params: { projectId: BC.currentProject.id } });
    crumbs.push({ label: 'Setup Wizard' });
  } else if (page === 'review' && BC.currentProject) {
    crumbs.push({ label: BC.currentProject.name || 'Project' });
    crumbs.push({ label: 'Review' });
  } else if (page === 'results' && BC.currentProject) {
    crumbs.push({ label: BC.currentProject.name || 'Project' });
    crumbs.push({ label: 'Results' });
  }

  if (crumbs.length <= 1) {
    bar.style.display = 'none';
    return;
  }
  bar.style.display = 'block';

  bc.innerHTML = crumbs.map((c, i) => {
    const isLast = i === crumbs.length - 1;
    const sep = i > 0 ? '<span class="breadcrumb-sep">›</span>' : '';
    if (isLast) return `${sep}<li class="breadcrumb-item active">${c.label}</li>`;
    const href = c.page ? `javascript:navigate('${c.page}', ${JSON.stringify(c.params || {})})` : '#';
    return `${sep}<li class="breadcrumb-item"><a href="${href}">${c.label}</a></li>`;
  }).join('');
}

// ── Toast Notifications ───────────────────────────────────────────────────────
function showToast(msg, type = 'info', duration = 4000) {
  const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
  const container = document.getElementById('toast-container');
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.innerHTML = `<span>${icons[type] || 'ℹ️'}</span><span>${msg}</span>`;
  container.appendChild(el);
  setTimeout(() => { el.style.opacity = '0'; el.style.transition = 'opacity .3s'; setTimeout(() => el.remove(), 300); }, duration);
}
window.showToast = showToast;

// ── System Status ─────────────────────────────────────────────────────────────
async function checkSystemStatus() {
  const dot   = document.getElementById('status-dot');
  const label = document.getElementById('status-label');
  dot.className = 'status-dot loading';
  label.textContent = 'Checking...';

  try {
    const s = await window.API.get('/system/check');
    BC.systemStatus = s;

    if (s.ambertools_available) {
      dot.className = 'status-dot ok';
      label.textContent = 'AmberTools ✓';
    } else if (s.wsl_available) {
      dot.className = 'status-dot warn';
      label.textContent = 'WSL OK · No AmberTools';
    } else {
      dot.className = 'status-dot warn';
      label.textContent = 'Demo / Generate mode';
    }
  } catch {
    dot.className = 'status-dot error';
    label.textContent = 'Server offline';
  }
}

// ── Accordion helper ──────────────────────────────────────────────────────────
function initAccordions(root = document) {
  root.querySelectorAll('.accordion-header').forEach(header => {
    header.addEventListener('click', () => {
      const item = header.closest('.accordion-item');
      item.classList.toggle('open');
    });
  });
}
window.initAccordions = initAccordions;

// ── Range slider helpers ──────────────────────────────────────────────────────
function initRangeSliders(root = document) {
  root.querySelectorAll('input[type="range"]').forEach(input => {
    const display = root.querySelector(`[data-for="${input.id}"]`);
    if (!display) return;
    const update = () => { display.textContent = input.value + (input.dataset.unit || ''); };
    input.addEventListener('input', update);
    update();
  });
}
window.initRangeSliders = initRangeSliders;

// ── Format helpers ────────────────────────────────────────────────────────────
function fmtDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString();
}
function fmtBytes(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}
window.fmtDate = fmtDate;
window.fmtBytes = fmtBytes;

function statusBadge(status) {
  const map = {
    new: 'badge-new', uploaded: 'badge-uploaded', configured: 'badge-configured',
    completed: 'badge-completed', running: 'badge-running', failed: 'badge-failed',
    queued: 'badge-queued', cancelled: 'badge-queued', success: 'badge-completed',
  };
  const cls = map[status] || 'badge-new';
  return `<span class="badge ${cls}">${status}</span>`;
}
window.statusBadge = statusBadge;

// ── Modal helpers ─────────────────────────────────────────────────────────────
document.getElementById('btn-help').addEventListener('click', () => {
  document.getElementById('help-modal').style.display = 'flex';
});
document.getElementById('help-modal-close').addEventListener('click', () => {
  document.getElementById('help-modal').style.display = 'none';
});
document.getElementById('help-modal').addEventListener('click', e => {
  if (e.target === e.currentTarget) e.currentTarget.style.display = 'none';
});

document.getElementById('nav-home-link').addEventListener('click', e => {
  e.preventDefault();
  navigate('dashboard');
});

// ── Boot ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  checkSystemStatus();
  navigate('dashboard');
});
