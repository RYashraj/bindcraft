/**
 * dashboard.js — Project list page
 */
async function renderDashboard(container) {
  container.innerHTML = `
    <div class="page">
      <div class="container">
        <!-- Hero -->
        <div class="hero">
          <div class="hero-tagline">🔬 B.Pharm Molecular Dynamics</div>
          <h1>Welcome to <span class="text-gradient">BindCraft</span></h1>
          <p class="hero-subtitle">
            Learn AMBER molecular dynamics step by step —
            no command-line experience required. Upload your protein–ligand complex,
            configure parameters, and generate or run your simulation.
          </p>
        </div>

        <!-- Setup Checklist + Projects side by side -->
        <div class="grid-2 mt-6">
          <!-- Left: System Status -->
          <div>
            <div class="section-header">
              <div class="section-icon">🖥️</div>
              <div>
                <div class="section-title">Environment</div>
                <div class="section-sub">Software availability on this machine</div>
              </div>
            </div>
            <ul class="checklist" id="checklist"></ul>

            <div class="disclaimer-box mt-4">
              <strong>⚠️ Educational Use Only</strong><br>
              BindCraft is designed for learning only. Results are not validated for
              clinical, docking, or publishable research.
              Ligand must already be in its binding pose — BindCraft does not perform docking.
            </div>
          </div>

          <!-- Right: Quick Start -->
          <div>
            <div class="section-header">
              <div class="section-icon">🚀</div>
              <div>
                <div class="section-title">Quick Start</div>
                <div class="section-sub">Three ways to use BindCraft</div>
              </div>
            </div>
            <div class="flex flex-col gap-3">
              <div class="card" style="padding: var(--space-4);">
                <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
                  <span style="font-size:1.4rem;">🧪</span>
                  <strong>Demo Mode</strong>
                  <span class="badge badge-demo">No setup needed</span>
                </div>
                <p class="text-sm" style="color:var(--text-secondary)">Explore a pre-built AChE + Donepezil simulation with charts and logs.</p>
              </div>
              <div class="card" style="padding: var(--space-4);">
                <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
                  <span style="font-size:1.4rem;">📦</span>
                  <strong>Generate Only</strong>
                  <span class="badge badge-uploaded">Windows OK</span>
                </div>
                <p class="text-sm" style="color:var(--text-secondary)">Create and download a complete AMBER input package. No WSL required.</p>
              </div>
              <div class="card" style="padding: var(--space-4);">
                <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
                  <span style="font-size:1.4rem;">⚡</span>
                  <strong>Run Local</strong>
                  <span class="badge badge-configured">WSL2 + AmberTools</span>
                </div>
                <p class="text-sm" style="color:var(--text-secondary)">Execute the full simulation pipeline locally. Requires WSL2 + Ubuntu + AmberTools (free).</p>
              </div>
            </div>
          </div>
        </div>

        <hr class="divider" />

        <!-- Projects -->
        <div class="section-header">
          <div class="section-icon">📁</div>
          <div>
            <div class="section-title">My Projects</div>
            <div class="section-sub">Create, open, or delete local MD projects</div>
          </div>
        </div>
        <div id="projects-grid" class="project-grid">
          <div class="page-loading" style="min-height:200px;grid-column:1/-1;">
            <div class="spinner-large"></div>
            <p>Loading projects…</p>
          </div>
        </div>
      </div>
    </div>
  `;

  // Load checklist
  renderChecklist();

  // Load projects
  try {
    const projects = await window.API.get('/projects/');
    renderProjectGrid(projects);
  } catch (e) {
    document.getElementById('projects-grid').innerHTML = `
      <div class="empty-state" style="grid-column:1/-1;">
        <div class="empty-state-icon">❌</div>
        <h3>Could not load projects</h3>
        <p>${e.message}</p>
      </div>`;
  }
}

// ── Checklist ────────────────────────────────────────────────────────────────
async function renderChecklist() {
  const list = document.getElementById('checklist');
  list.innerHTML = `<li class="checklist-item loading"><span class="check-icon"><div class="spinner"></div></span><div><div class="check-label">Checking environment…</div></div></li>`;

  const s = BC.systemStatus || (await window.API.get('/system/check').catch(() => null));
  BC.systemStatus = s;
  if (!s) {
    list.innerHTML = `<li class="checklist-item fail"><span class="check-icon">❌</span><div><div class="check-label">Server not reachable</div><div class="check-detail">Make sure start.bat is running.</div></div></li>`;
    return;
  }

  const items = [
    {
      label: 'Python & FastAPI',
      pass: true,
      detail: s.python_version?.split(' ')[0] || 'OK',
    },
    {
      label: 'WSL2 (Windows Subsystem for Linux)',
      pass: s.wsl_available,
      warn: false,
      detail: s.wsl_available
        ? `Distro: ${s.wsl_distro}`
        : 'Not detected. Run mode disabled. Install WSL2 from Microsoft Store.',
    },
    {
      label: 'AmberTools (free)',
      pass: s.ambertools_available,
      warn: s.wsl_available && !s.ambertools_available,
      detail: s.ambertools_available
        ? 'pdb4amber, antechamber, sander, cpptraj — all found'
        : s.wsl_available
          ? 'Install: conda create -n ambertools ambertools -c conda-forge'
          : 'Requires WSL2 first.',
    },
    {
      label: 'Disk Space',
      pass: s.disk_free_gb > 2,
      warn: s.disk_free_gb > 0.5 && s.disk_free_gb <= 2,
      detail: s.disk_free_gb > 0
        ? `${s.disk_free_gb} GB free${s.disk_free_gb < 2 ? ' (low — simulations may fail)' : ''}`
        : 'Could not determine',
    },
  ];

  list.innerHTML = items.map(it => {
    const cls = it.pass ? 'pass' : it.warn ? 'warn' : 'fail';
    const icon = it.pass ? '✅' : it.warn ? '⚠️' : '❌';
    return `
      <li class="checklist-item ${cls}">
        <span class="check-icon">${icon}</span>
        <div>
          <div class="check-label">${it.label}</div>
          <div class="check-detail">${it.detail}</div>
        </div>
      </li>`;
  }).join('');
}

// ── Project Grid ─────────────────────────────────────────────────────────────
function renderProjectGrid(projects) {
  const grid = document.getElementById('projects-grid');

  const cards = projects.map(p => projectCard(p)).join('');
  grid.innerHTML = cards + newProjectCard();

  // Bind open buttons
  grid.querySelectorAll('[data-open-project]').forEach(btn => {
    btn.addEventListener('click', e => {
      e.stopPropagation();
      openProject(btn.dataset.openProject, projects);
    });
  });

  // Bind delete buttons
  grid.querySelectorAll('[data-delete-project]').forEach(btn => {
    btn.addEventListener('click', async e => {
      e.stopPropagation();
      await deleteProject(btn.dataset.deleteProject);
    });
  });

  // Bind new project card
  grid.querySelector('#new-project-card')?.addEventListener('click', () => {
    navigate('new-project');
  });
}

function projectCard(p) {
  const isDemo = p.id === 'demo-acetylcholinesterase';
  const demoTag = isDemo ? '<span class="badge badge-demo">🧪 Demo</span>' : '';
  const date = p.created_at ? new Date(p.created_at).toLocaleDateString() : '';
  const ligInfo = p.ligand_name ? `<span class="tag">${p.ligand_name}</span>` : '';
  const ffInfo  = p.settings_json ? '<span class="tag">ff14SB · GAFF2</span>' : '';

  return `
    <div class="project-card" data-open-project="${p.id}">
      <div class="project-card-top">
        <div>
          <div class="project-name">${escHtml(p.name)}</div>
          ${statusBadge(p.status)} ${demoTag}
        </div>
      </div>
      ${p.notes ? `<div class="project-notes">${escHtml(p.notes)}</div>` : ''}
      <div class="project-meta">
        ${ligInfo} ${ffInfo}
        <span style="margin-left:auto;font-size:.75rem;color:var(--text-muted)">📅 ${date}</span>
      </div>
      <div class="project-actions">
        <button class="btn btn-primary btn-sm" data-open-project="${p.id}">
          ${p.status === 'completed' ? '📊 View Results' : '▶ Open'}
        </button>
        ${!isDemo ? `<button class="btn btn-danger btn-sm" data-delete-project="${p.id}" title="Delete project">🗑</button>` : ''}
      </div>
    </div>`;
}

function newProjectCard() {
  return `
    <div class="project-card project-card-new" id="new-project-card" role="button" tabindex="0">
      <div class="plus-icon">+</div>
      <div>New Project</div>
      <div class="text-xs" style="margin-top:4px;">Upload complex PDB + ligand</div>
    </div>`;
}

async function openProject(id, projects) {
  const project = projects.find(p => p.id === id) || await window.API.get(`/projects/${id}`).catch(() => null);
  if (!project) return showToast('Project not found.', 'error');

  BC.currentProject = project;

  if (project.status === 'completed' || project.status === 'uploaded' && project.settings_json) {
    navigate('results', { projectId: id });
  } else if (project.status === 'configured' || project.status === 'uploaded') {
    navigate('review', { projectId: id });
  } else {
    navigate('new-project', { projectId: id });
  }
}

async function deleteProject(id) {
  if (!confirm('Delete this project and all its files? This cannot be undone.')) return;
  try {
    await window.API.delete(`/projects/${id}`);
    showToast('Project deleted.', 'success');
    navigate('dashboard');
  } catch (e) {
    showToast(`Delete failed: ${e.message}`, 'error');
  }
}

function escHtml(str) {
  if (!str) return '';
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
window.escHtml = escHtml;
