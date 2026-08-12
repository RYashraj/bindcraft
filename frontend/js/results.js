/**
 * results.js — Job status polling, log tailing, charts (Plotly), and file downloads.
 */
let pollInterval = null;

async function renderResults(container, params = {}) {
  const projectId = params.projectId || BC.currentProject?.id;
  if (!projectId) { navigate('dashboard'); return; }

  // Clean up any existing poll
  if (pollInterval) clearInterval(pollInterval);

  let project = BC.currentProject?.id === projectId ? BC.currentProject : null;
  if (!project) {
    try { project = await window.API.get(`/projects/${projectId}`); BC.currentProject = project; }
    catch { showToast('Could not load project', 'error'); navigate('dashboard'); return; }
  }

  // Get jobs
  let jobs = [];
  try { jobs = await window.API.get(`/jobs/?project_id=${projectId}`); } catch {}
  let activeJob = jobs[0]; // Most recent job

  container.innerHTML = `
    <div class="page">
      <div class="container">
        <!-- Status Banner -->
        <div id="status-banner" class="status-banner queued">
          <div class="status-icon" id="status-icon">⏳</div>
          <div class="status-text">
            <div class="status-title" id="status-title">Loading...</div>
            <div class="status-sub" id="status-sub">Checking job status</div>
          </div>
          <div id="status-actions"></div>
        </div>

        <!-- Download & Actions Row -->
        <div class="flex items-center justify-between mb-6">
          <div class="flex gap-3">
            <button class="btn btn-primary" id="btn-download" disabled>
              📥 Download ZIP
            </button>
            <a href="/api/projects/${projectId}/files/report/index.html" target="_blank"
               class="btn btn-secondary" id="btn-report" style="display:none">
              📄 View Report
            </a>
          </div>
          <button class="btn btn-ghost" onclick="navigate('dashboard')">Close</button>
        </div>

        <div class="grid-2">
          <!-- Left: Logs -->
          <div class="card" style="display:flex; flex-direction:column; height:450px;">
            <div class="card-header" style="margin-bottom:0;">
              <h3 style="margin:0">Terminal Output</h3>
              <span class="badge" id="log-badge" style="display:none">Live</span>
            </div>
            <pre class="log-viewer" id="log-viewer" style="flex:1; border:none; margin:0; border-radius:0 0 var(--radius-md) var(--radius-md); max-height:none;">Loading logs...</pre>
          </div>

          <!-- Right: Files -->
          <div class="card" style="display:flex; flex-direction:column; height:450px;">
            <div class="card-header">
              <h3 style="margin:0">Generated Files</h3>
              <button class="btn btn-ghost btn-sm" id="btn-refresh-files">↻</button>
            </div>
            <div class="file-tree" id="file-tree" style="flex:1; overflow-y:auto; padding-right:8px;">
              <div class="text-muted text-sm" style="padding:var(--space-2)">No files generated yet.</div>
            </div>
          </div>
        </div>

        <!-- Charts (Hidden until completed) -->
        <div id="charts-area" style="display:none; margin-top:var(--space-8)">
          <div class="section-header">
            <div class="section-icon">📈</div>
            <div>
              <div class="section-title">Analysis</div>
              <div class="section-sub">Trajectories and energy profiles</div>
            </div>
          </div>

          <div class="chart-grid">
            <div class="chart-card">
              <div class="chart-title">Potential Energy <span>(kcal/mol)</span></div>
              <div id="chart-energy" class="chart-container"></div>
            </div>
            <div class="chart-card">
              <div class="chart-title">Temperature <span>(K)</span></div>
              <div id="chart-temp" class="chart-container"></div>
            </div>
            <div class="chart-card">
              <div class="chart-title">Backbone RMSD <span>(Å)</span></div>
              <div id="chart-rmsd" class="chart-container"></div>
            </div>
            <div class="chart-card">
              <div class="chart-title">Per-Residue RMSF <span>(Å)</span></div>
              <div id="chart-rmsf" class="chart-container"></div>
            </div>
          </div>
        </div>

      </div>
    </div>
  `;

  // Actions
  document.getElementById('btn-download').addEventListener('click', () => {
    window.location.href = `/api/projects/${projectId}/download`;
  });
  document.getElementById('btn-refresh-files').addEventListener('click', () => updateFiles(projectId));

  // Initial update
  await updateStatus();
  updateFiles(projectId);

  // Polling logic
  async function updateStatus() {
    if (!activeJob) {
      // Try to refetch jobs
      try { jobs = await window.API.get(`/jobs/?project_id=${projectId}`); activeJob = jobs[0]; } catch {}
      if (!activeJob) {
        setStatusUI('queued', 'No Jobs Found', 'This project has not been run yet.');
        return;
      }
    } else {
      try { activeJob = await window.API.get(`/jobs/${activeJob.id}`); } catch {}
    }

    const { status, mode, current_step, error_msg } = activeJob;

    // Update Logs
    try {
      const logs = await window.API.get(`/jobs/${activeJob.id}/logs`);
      const viewer = document.getElementById('log-viewer');
      // Only auto-scroll if we're near the bottom
      const isScrolledToBottom = viewer.scrollHeight - viewer.clientHeight <= viewer.scrollTop + 50;
      viewer.textContent = logs.log || 'Waiting for output...';
      if (isScrolledToBottom) viewer.scrollTop = viewer.scrollHeight;
    } catch {}

    // Update UI based on status
    if (status === 'queued') {
      setStatusUI('queued', 'Job Queued', 'Waiting for worker...', mode);
    } else if (status === 'running') {
      setStatusUI('running', 'Running', current_step || 'Processing...', mode, true);
      document.getElementById('log-badge').style.display = 'inline-flex';
    } else if (status === 'success') {
      setStatusUI('success', 'Complete', mode === 'generate' ? 'Input files generated.' : 'Simulation finished successfully.', mode);
      document.getElementById('log-badge').style.display = 'none';
      document.getElementById('btn-download').disabled = false;
      document.getElementById('btn-report').style.display = 'inline-flex';
      if (mode === 'run' || mode === 'demo') {
        document.getElementById('charts-area').style.display = 'block';
        loadCharts(projectId);
      }
    } else if (status === 'failed') {
      setStatusUI('failed', 'Failed', error_msg || 'An unknown error occurred.', mode);
      document.getElementById('log-badge').style.display = 'none';
    } else if (status === 'cancelled') {
      setStatusUI('cancelled', 'Cancelled', 'Job was stopped by user.', mode);
      document.getElementById('log-badge').style.display = 'none';
    }

    // Continue polling if running
    if (status === 'queued' || status === 'running') {
      if (!pollInterval) pollInterval = setInterval(() => { updateStatus(); updateFiles(projectId); }, 2000);
    } else {
      if (pollInterval) { clearInterval(pollInterval); pollInterval = null; }
    }
  }

  // File tree
  async function updateFiles(projId) {
    try {
      const files = await window.API.get(`/projects/${projId}/files`);
      if (!files.length) return;

      // Group by category
      const groups = {};
      files.forEach(f => {
        if (!groups[f.category]) groups[f.category] = [];
        groups[f.category].push(f);
      });

      let html = '';
      const order = ['input', 'output', 'analysis', 'logs', 'report'];
      for (const cat of order) {
        if (!groups[cat]) continue;
        html += `<div class="file-category">${cat}</div>`;
        groups[cat].forEach(f => {
          html += `
            <a href="/api/projects/${projId}/files${f.path}" target="_blank" class="file-entry" title="Click to view/download">
              📄 ${f.name}
              <span class="file-size">${fmtBytes(f.size_bytes)}</span>
            </a>
          `;
        });
      }
      document.getElementById('file-tree').innerHTML = html;
    } catch {}
  }

  // Cancel action helper
  window._cancelJob = async () => {
    if (!activeJob) return;
    try {
      await window.API.post(`/jobs/${activeJob.id}/cancel`);
      showToast('Job cancelled', 'info');
      updateStatus();
    } catch (e) {
      showToast(`Failed to cancel: ${e.message}`, 'error');
    }
  };
}

function setStatusUI(cls, title, sub, mode, canCancel = false) {
  const banner = document.getElementById('status-banner');
  const icon = document.getElementById('status-icon');
  banner.className = `status-banner ${cls}`;

  const icons = { queued: '⏳', running: '<div class="spinner"></div>', success: '✅', failed: '❌', cancelled: '⏹' };
  icon.innerHTML = icons[cls] || 'ℹ️';

  document.getElementById('status-title').textContent = title + (mode ? ` (${mode})` : '');
  document.getElementById('status-sub').textContent = sub;

  const actions = document.getElementById('status-actions');
  if (canCancel) {
    actions.innerHTML = `<button class="btn btn-danger btn-sm" onclick="_cancelJob()">Cancel</button>`;
  } else {
    actions.innerHTML = '';
  }
}

// ── Charts ────────────────────────────────────────────────────────────────────
async function loadCharts(projectId) {
  try {
    const data = await window.API.get(`/projects/${projectId}/charts`);

    const layoutBase = {
      margin: { t: 10, r: 10, b: 30, l: 50 },
      paper_bgcolor: 'transparent',
      plot_bgcolor: 'transparent',
      font: { color: '#94a3b8', family: 'Inter' },
      xaxis: { gridcolor: '#1e293b', zerolinecolor: '#1e293b' },
      yaxis: { gridcolor: '#1e293b', zerolinecolor: '#1e293b' },
      showlegend: false,
    };

    const config = { responsive: true, displayModeBar: false };

    // Group energy/temp by stage (min, heat, equil, prod) for coloring
    const plotStages = (containerId, dataset, yTitle) => {
      if (!dataset || !dataset.length) {
        document.getElementById(containerId).innerHTML = '<div class="empty-state" style="padding:20px">No data</div>';
        return;
      }

      const stages = [...new Set(dataset.map(d => d.stage))];
      const colors = { min: '#a78bfa', heat: '#f472b6', equil: '#fbbf24', prod: '#38bdf8' };

      const traces = stages.map(st => {
        const pts = dataset.filter(d => d.stage === st);
        return {
          x: pts.map(d => d.x),
          y: pts.map(d => d.y),
          type: 'scatter',
          mode: 'lines',
          name: st,
          line: { color: colors[st] || '#818cf8', width: 2 }
        };
      });

      Plotly.newPlot(containerId, traces, {
        ...layoutBase,
        yaxis: { ...layoutBase.yaxis, title: yTitle },
        showlegend: true,
        legend: { orientation: 'h', y: 1.1, font: { size: 10 } }
      }, config);
    };

    plotStages('chart-energy', data.energy, 'Etot');
    plotStages('chart-temp', data.temperature, 'Temp');

    // Single line plots for RMSD, RMSF, Rg
    const plotSingle = (containerId, dataset, color) => {
      if (!dataset || !dataset.length) {
        document.getElementById(containerId).innerHTML = '<div class="empty-state" style="padding:20px">No data</div>';
        return;
      }
      Plotly.newPlot(containerId, [{
        x: dataset.map(d => d.x),
        y: dataset.map(d => d.y),
        type: 'scatter',
        mode: 'lines',
        line: { color: color, width: 2 }
      }], layoutBase, config);
    };

    plotSingle('chart-rmsd', data.rmsd, '#34d399'); // emerald
    plotSingle('chart-rmsf', data.rmsf, '#f87171'); // red
    // Only Plotly has trouble with missing divs, so just ignore Rg if no div
    if(document.getElementById('chart-rg')) {
       plotSingle('chart-rg', data.rg, '#a78bfa'); // violet
    }

  } catch (e) {
    console.warn("Failed to load charts", e);
  }
}

// Cleanup on unmount (SPA hack)
const origNavigate = window.navigate;
window.navigate = function(...args) {
  if (pollInterval) { clearInterval(pollInterval); pollInterval = null; }
  origNavigate(...args);
};
